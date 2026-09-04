"""Track non-clinical lost-property custody and release readiness."""

from dataclasses import dataclass
from datetime import datetime

from .models import DomainError


@dataclass(frozen=True, slots=True)
class LostPropertyItem:
    item_id: str
    storage_location: str
    received_at: datetime
    sealed: bool
    sensitive: bool = False


@dataclass(frozen=True, slots=True)
class LostPropertyClaim:
    item_id: str
    claimant_id: str
    identity_verified: bool
    description_matched: bool
    second_reviewer: str | None = None


@dataclass(frozen=True, slots=True)
class LostPropertyDecision:
    item_id: str
    claimant_id: str | None
    decision: str
    blockers: tuple[str, ...]


def assess_lost_property_release(
    items: list[LostPropertyItem], claims: list[LostPropertyClaim], *, as_of: datetime
) -> list[LostPropertyDecision]:
    """Require identity, description, seal, and dual review for sensitive items."""
    if as_of.tzinfo is None:
        raise DomainError("lost-property assessment time must be timezone-aware")
    inventory: dict[str, LostPropertyItem] = {}
    for item in items:
        item_id = _text(item.item_id, "lost-property item id")
        location = _text(item.storage_location, "lost-property storage location")
        key = item_id.casefold()
        if key in inventory or item.received_at.tzinfo is None or item.received_at > as_of:
            raise DomainError("invalid or duplicate lost-property item")
        inventory[key] = LostPropertyItem(item_id, location, item.received_at, item.sealed, item.sensitive)
    by_item: dict[str, LostPropertyClaim] = {}
    for claim in claims:
        item_id = _text(claim.item_id, "lost-property claim item")
        claimant_id = _text(claim.claimant_id, "lost-property claimant")
        key = item_id.casefold()
        if key not in inventory or key in by_item:
            raise DomainError("invalid or duplicate lost-property claim")
        by_item[key] = LostPropertyClaim(
            item_id, claimant_id, claim.identity_verified, claim.description_matched, claim.second_reviewer
        )
    decisions: list[LostPropertyDecision] = []
    for key, item in inventory.items():
        matched_claim = by_item.get(key)
        if matched_claim is None:
            decisions.append(LostPropertyDecision(item.item_id, None, "retain", ("claim_missing",)))
            continue
        blockers: list[str] = []
        if not item.sealed:
            blockers.append("custody_seal_broken")
        if not matched_claim.identity_verified:
            blockers.append("identity_not_verified")
        if not matched_claim.description_matched:
            blockers.append("description_not_matched")
        if item.sensitive and not matched_claim.second_reviewer:
            blockers.append("second_reviewer_missing")
        decisions.append(
            LostPropertyDecision(
                item.item_id, matched_claim.claimant_id, "release" if not blockers else "hold", tuple(blockers)
            )
        )
    return sorted(decisions, key=lambda row: (row.decision == "release", -len(row.blockers), row.item_id))


def _text(value: str, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise DomainError(f"{field} is required")
    return normalized
