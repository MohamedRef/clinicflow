"""Non-clinical supply shortage, substitution, allocation, and approval controls."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum


class StockCriticality(StrEnum):
    ROUTINE = "routine"
    IMPORTANT = "important"
    ESSENTIAL = "essential"


class SubstitutionState(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class StockItem:
    sku: str
    site_id: str
    category: str
    units_available: int
    units_reserved: int
    expires_at: datetime | None
    criticality: StockCriticality
    attributes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StockDemand:
    demand_id: str
    site_id: str
    requested_sku: str
    category: str
    units_required: int
    needed_at: datetime
    priority: int
    required_attributes: tuple[str, ...] = ()
    substitution_allowed: bool = False


@dataclass(frozen=True, slots=True)
class SubstitutionProposal:
    proposal_id: str
    demand_id: str
    substitute_sku: str
    proposed_at: datetime
    proposed_by: str
    valid_until: datetime
    rationale: str
    state: SubstitutionState = SubstitutionState.PROPOSED
    approved_at: datetime | None = None
    approved_by: str | None = None


@dataclass(frozen=True, slots=True)
class StockAllocation:
    allocation_id: str
    demand_id: str
    sku: str
    units: int
    allocated_at: datetime
    substituted: bool


@dataclass(frozen=True, slots=True)
class StockDecision:
    demand_id: str
    requested_sku: str
    selected_sku: str | None
    units_available: int
    units_required: int
    shortfall: int
    proposal_id: str | None
    ready: bool
    blockers: tuple[str, ...]


def _text(value: str, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field} is required")
    return normalized


def _instant(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _non_negative(value: int, field: str) -> int:
    if isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def _positive(value: int, field: str) -> int:
    result = _non_negative(value, field)
    if result == 0:
        raise ValueError(f"{field} must be positive")
    return result


def _unique(values: Iterable[str], field: str) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _text(value, field).casefold()
        if normalized in seen:
            raise ValueError(f"duplicate {field}: {normalized}")
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


class StockSubstitutionBoard:
    """Select safe stock, gate substitutions, and reserve inventory atomically."""

    def __init__(self) -> None:
        self._stock: dict[str, StockItem] = {}
        self._demands: dict[str, StockDemand] = {}
        self._proposals: dict[str, SubstitutionProposal] = {}
        self._allocations: dict[str, StockAllocation] = {}

    def add_stock(self, item: StockItem) -> StockItem:
        sku = _text(item.sku, "stock sku")
        site_id = _text(item.site_id, "stock site id").casefold()
        category = _text(item.category, "stock category").casefold()
        available = _non_negative(item.units_available, "stock units available")
        reserved = _non_negative(item.units_reserved, "stock units reserved")
        if reserved > available:
            raise ValueError("reserved stock cannot exceed available units")
        expires = None if item.expires_at is None else _instant(item.expires_at, "stock expiry")
        key = f"{site_id}:{sku.casefold()}"
        if key in self._stock:
            raise ValueError(f"duplicate site stock item: {sku}")
        normalized = StockItem(
            sku=sku,
            site_id=site_id,
            category=category,
            units_available=available,
            units_reserved=reserved,
            expires_at=expires,
            criticality=item.criticality,
            attributes=_unique(item.attributes, "stock attribute"),
        )
        self._stock[key] = normalized
        return normalized

    def request(self, demand: StockDemand) -> StockDemand:
        demand_id = _text(demand.demand_id, "stock demand id")
        key = demand_id.casefold()
        if key in self._demands:
            raise ValueError(f"duplicate stock demand: {demand_id}")
        normalized = StockDemand(
            demand_id=demand_id,
            site_id=_text(demand.site_id, "demand site id").casefold(),
            requested_sku=_text(demand.requested_sku, "requested sku"),
            category=_text(demand.category, "demand category").casefold(),
            units_required=_positive(demand.units_required, "required stock units"),
            needed_at=_instant(demand.needed_at, "stock needed at"),
            priority=_positive(demand.priority, "stock demand priority"),
            required_attributes=_unique(demand.required_attributes, "required stock attribute"),
            substitution_allowed=demand.substitution_allowed,
        )
        self._demands[key] = normalized
        return normalized

    def propose(self, proposal: SubstitutionProposal) -> SubstitutionProposal:
        proposal_id = _text(proposal.proposal_id, "substitution proposal id")
        key = proposal_id.casefold()
        if key in self._proposals:
            raise ValueError(f"duplicate substitution proposal: {proposal_id}")
        demand = self._demand(proposal.demand_id)
        if not demand.substitution_allowed:
            raise ValueError("stock demand does not allow substitution")
        substitute = self._item(demand.site_id, proposal.substitute_sku)
        proposed_at = _instant(proposal.proposed_at, "proposal time")
        valid_until = _instant(proposal.valid_until, "proposal validity")
        if valid_until <= proposed_at or valid_until > demand.needed_at:
            raise ValueError("proposal validity must end after proposal and no later than need")
        blockers = self._compatibility_blockers(demand, substitute, proposed_at)
        if blockers:
            raise ValueError("unsafe stock substitution: " + "; ".join(blockers))
        normalized = SubstitutionProposal(
            proposal_id=proposal_id,
            demand_id=demand.demand_id,
            substitute_sku=substitute.sku,
            proposed_at=proposed_at,
            proposed_by=_text(proposal.proposed_by, "proposal author"),
            valid_until=valid_until,
            rationale=_text(proposal.rationale, "proposal rationale"),
        )
        self._proposals[key] = normalized
        return normalized

    def approve(self, proposal_id: str, approved_at: datetime, approved_by: str) -> SubstitutionProposal:
        key, proposal = self._proposal(proposal_id)
        approved = _instant(approved_at, "approved at")
        actor = _text(approved_by, "substitution approver")
        if proposal.state is not SubstitutionState.PROPOSED:
            raise ValueError("only proposed substitutions can be approved")
        if approved < proposal.proposed_at or approved > proposal.valid_until:
            raise ValueError("approval must occur during proposal validity")
        if actor.casefold() == proposal.proposed_by.casefold():
            raise ValueError("substitution requires independent approval")
        updated = replace(
            proposal,
            state=SubstitutionState.APPROVED,
            approved_at=approved,
            approved_by=actor,
        )
        self._proposals[key] = updated
        return updated

    def reject(self, proposal_id: str, rejected_at: datetime, reason: str) -> SubstitutionProposal:
        key, proposal = self._proposal(proposal_id)
        rejected = _instant(rejected_at, "rejected at")
        _text(reason, "rejection reason")
        if proposal.state is not SubstitutionState.PROPOSED or rejected < proposal.proposed_at:
            raise ValueError("only active proposals can be rejected")
        updated = replace(proposal, state=SubstitutionState.REJECTED)
        self._proposals[key] = updated
        return updated

    def expire(self, as_of: datetime) -> tuple[SubstitutionProposal, ...]:
        now = _instant(as_of, "as of")
        expired: list[SubstitutionProposal] = []
        for key, proposal in self._proposals.items():
            if proposal.state is not SubstitutionState.PROPOSED or proposal.valid_until >= now:
                continue
            updated = replace(proposal, state=SubstitutionState.EXPIRED)
            self._proposals[key] = updated
            expired.append(updated)
        expired.sort(key=lambda item: (item.valid_until, item.proposal_id))
        return tuple(expired)

    def decision(self, demand_id: str, as_of: datetime) -> StockDecision:
        demand = self._demand(demand_id)
        now = _instant(as_of, "as of")
        requested = self._stock.get(f"{demand.site_id}:{demand.requested_sku.casefold()}")
        requested_blockers = ["requested stock is unavailable"]
        if requested is not None:
            requested_blockers = self._compatibility_blockers(demand, requested, now)
            if not requested_blockers:
                free = requested.units_available - requested.units_reserved
                shortfall = max(0, demand.units_required - free)
                return StockDecision(
                    demand.demand_id,
                    demand.requested_sku,
                    requested.sku,
                    free,
                    demand.units_required,
                    shortfall,
                    None,
                    shortfall == 0,
                    () if shortfall == 0 else (f"requested stock short by {shortfall}",),
                )
        proposals = [
            proposal
            for proposal in self._proposals.values()
            if proposal.demand_id.casefold() == demand.demand_id.casefold()
            and proposal.state is SubstitutionState.APPROVED
            and proposal.valid_until >= now
        ]
        proposals.sort(key=lambda item: (item.approved_at or item.proposed_at, item.proposal_id))
        if proposals:
            proposal = proposals[0]
            substitute = self._item(demand.site_id, proposal.substitute_sku)
            blockers = self._compatibility_blockers(demand, substitute, now)
            free = substitute.units_available - substitute.units_reserved
            shortfall = max(0, demand.units_required - free)
            if shortfall:
                blockers.append(f"substitute stock short by {shortfall}")
            return StockDecision(
                demand.demand_id,
                demand.requested_sku,
                substitute.sku,
                free,
                demand.units_required,
                shortfall,
                proposal.proposal_id,
                not blockers,
                tuple(blockers),
            )
        return StockDecision(
            demand.demand_id,
            demand.requested_sku,
            None,
            0,
            demand.units_required,
            demand.units_required,
            None,
            False,
            tuple((*requested_blockers, "no approved substitution")),
        )

    def allocate(self, demand_id: str, allocated_at: datetime) -> StockAllocation:
        now = _instant(allocated_at, "allocated at")
        demand = self._demand(demand_id)
        decision = self.decision(demand_id, now)
        if not decision.ready or decision.selected_sku is None:
            raise ValueError("stock demand is not ready to allocate")
        if any(item.demand_id.casefold() == demand.demand_id.casefold() for item in self._allocations.values()):
            raise ValueError("stock demand is already allocated")
        item = self._item(demand.site_id, decision.selected_sku)
        updated = replace(item, units_reserved=item.units_reserved + demand.units_required)
        self._stock[f"{item.site_id}:{item.sku.casefold()}"] = updated
        allocation = StockAllocation(
            allocation_id=f"allocation:{demand.demand_id}",
            demand_id=demand.demand_id,
            sku=item.sku,
            units=demand.units_required,
            allocated_at=now,
            substituted=item.sku.casefold() != demand.requested_sku.casefold(),
        )
        self._allocations[allocation.allocation_id.casefold()] = allocation
        return allocation

    def shortage_queue(self, as_of: datetime) -> tuple[StockDecision, ...]:
        now = _instant(as_of, "as of")
        decisions = [self.decision(demand.demand_id, now) for demand in self._demands.values()]
        pending = [decision for decision in decisions if not decision.ready]
        pending.sort(
            key=lambda decision: (
                -self._demand(decision.demand_id).priority,
                self._demand(decision.demand_id).needed_at,
                decision.demand_id,
            )
        )
        return tuple(pending)

    def _compatibility_blockers(self, demand: StockDemand, item: StockItem, as_of: datetime) -> list[str]:
        blockers: list[str] = []
        if item.category != demand.category:
            blockers.append("stock category does not match demand")
        missing = sorted(set(demand.required_attributes) - set(item.attributes))
        if missing:
            blockers.append("stock lacks attributes: " + ", ".join(missing))
        if item.expires_at is not None and item.expires_at <= max(as_of, demand.needed_at):
            blockers.append("stock expires before use")
        return blockers

    def _demand(self, demand_id: str) -> StockDemand:
        normalized = _text(demand_id, "stock demand id")
        try:
            return self._demands[normalized.casefold()]
        except KeyError as exc:
            raise KeyError(f"unknown stock demand: {normalized}") from exc

    def _item(self, site_id: str, sku: str) -> StockItem:
        site = _text(site_id, "stock site id").casefold()
        normalized_sku = _text(sku, "stock sku")
        try:
            return self._stock[f"{site}:{normalized_sku.casefold()}"]
        except KeyError as exc:
            raise KeyError(f"unknown site stock item: {normalized_sku}") from exc

    def _proposal(self, proposal_id: str) -> tuple[str, SubstitutionProposal]:
        normalized = _text(proposal_id, "substitution proposal id")
        key = normalized.casefold()
        try:
            return key, self._proposals[key]
        except KeyError as exc:
            raise KeyError(f"unknown substitution proposal: {normalized}") from exc
