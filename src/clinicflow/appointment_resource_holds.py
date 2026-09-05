"""Atomic room, staff, equipment, and interpreter holds for appointments."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class ResourceKind(StrEnum):
    ROOM = "room"
    STAFF = "staff"
    EQUIPMENT = "equipment"
    INTERPRETER = "interpreter"


class HoldState(StrEnum):
    HELD = "held"
    CONFIRMED = "confirmed"
    RELEASED = "released"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class AppointmentResource:
    resource_id: str
    kind: ResourceKind
    site_id: str
    capabilities: tuple[str, ...]
    available_from: datetime
    available_until: datetime
    active: bool = True


@dataclass(frozen=True, slots=True)
class ResourceRequirement:
    requirement_id: str
    kind: ResourceKind
    capabilities: tuple[str, ...]
    quantity: int = 1


@dataclass(frozen=True, slots=True)
class AppointmentDemand:
    appointment_id: str
    site_id: str
    starts_at: datetime
    ends_at: datetime
    priority: int
    requirements: tuple[ResourceRequirement, ...]


@dataclass(frozen=True, slots=True)
class ResourceHold:
    hold_id: str
    appointment_id: str
    requirement_id: str
    resource_id: str
    held_at: datetime
    expires_at: datetime
    state: HoldState
    confirmed_at: datetime | None = None
    released_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RequirementPlan:
    requirement_id: str
    resource_ids: tuple[str, ...]
    shortfall: int


@dataclass(frozen=True, slots=True)
class AppointmentResourcePlan:
    appointment_id: str
    requirements: tuple[RequirementPlan, ...]
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


def _positive(value: int, field: str) -> int:
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field} must be positive")
    return value


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


class AppointmentResourceBoard:
    """Allocate all appointment requirements before confirming any hold."""

    def __init__(
        self,
        resources: Iterable[AppointmentResource] = (),
        demands: Iterable[AppointmentDemand] = (),
        holds: Iterable[ResourceHold] = (),
    ) -> None:
        self._resources: dict[str, AppointmentResource] = {}
        self._demands: dict[str, AppointmentDemand] = {}
        self._holds: dict[str, ResourceHold] = {}
        for resource in resources:
            self.add_resource(resource)
        for demand in demands:
            self.add_demand(demand)
        for hold in holds:
            self._load_hold(hold)

    def _normalize_resource(self, resource: AppointmentResource) -> AppointmentResource:
        available_from = _instant(resource.available_from, "resource availability start")
        available_until = _instant(resource.available_until, "resource availability end")
        if available_until <= available_from:
            raise ValueError("resource availability end must follow start")
        return AppointmentResource(
            resource_id=_text(resource.resource_id, "resource id"),
            kind=resource.kind,
            site_id=_text(resource.site_id, "resource site id").casefold(),
            capabilities=_unique(resource.capabilities, "resource capability"),
            available_from=available_from,
            available_until=available_until,
            active=resource.active,
        )

    def _normalize_requirement(self, requirement: ResourceRequirement) -> ResourceRequirement:
        return ResourceRequirement(
            requirement_id=_text(requirement.requirement_id, "requirement id"),
            kind=requirement.kind,
            capabilities=_unique(requirement.capabilities, "required capability"),
            quantity=_positive(requirement.quantity, "requirement quantity"),
        )

    def _normalize_demand(self, demand: AppointmentDemand) -> AppointmentDemand:
        starts_at = _instant(demand.starts_at, "appointment start")
        ends_at = _instant(demand.ends_at, "appointment end")
        if ends_at <= starts_at:
            raise ValueError("appointment end must follow start")
        if ends_at - starts_at > timedelta(hours=24):
            raise ValueError("appointment resource window cannot exceed 24 hours")
        requirements = tuple(self._normalize_requirement(item) for item in demand.requirements)
        if not requirements:
            raise ValueError("appointment requires at least one resource")
        identities = [item.requirement_id.casefold() for item in requirements]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate appointment requirement")
        return AppointmentDemand(
            appointment_id=_text(demand.appointment_id, "appointment id"),
            site_id=_text(demand.site_id, "appointment site id").casefold(),
            starts_at=starts_at,
            ends_at=ends_at,
            priority=_positive(demand.priority, "appointment priority"),
            requirements=requirements,
        )

    def _normalize_hold(self, hold: ResourceHold) -> ResourceHold:
        held_at = _instant(hold.held_at, "hold time")
        expires_at = _instant(hold.expires_at, "hold expiry")
        if expires_at <= held_at:
            raise ValueError("resource hold expiry must follow hold time")
        confirmed_at = None if hold.confirmed_at is None else _instant(hold.confirmed_at, "confirmation time")
        released_at = None if hold.released_at is None else _instant(hold.released_at, "release time")
        if confirmed_at is not None and (confirmed_at < held_at or confirmed_at > expires_at):
            raise ValueError("confirmation must occur during hold window")
        if released_at is not None and released_at < held_at:
            raise ValueError("release cannot predate hold")
        return ResourceHold(
            hold_id=_text(hold.hold_id, "hold id"),
            appointment_id=_text(hold.appointment_id, "hold appointment id"),
            requirement_id=_text(hold.requirement_id, "hold requirement id"),
            resource_id=_text(hold.resource_id, "hold resource id"),
            held_at=held_at,
            expires_at=expires_at,
            state=hold.state,
            confirmed_at=confirmed_at,
            released_at=released_at,
        )

    def add_resource(self, resource: AppointmentResource) -> AppointmentResource:
        normalized = self._normalize_resource(resource)
        key = normalized.resource_id.casefold()
        if key in self._resources:
            raise ValueError(f"duplicate appointment resource: {normalized.resource_id}")
        self._resources[key] = normalized
        return normalized

    def add_demand(self, demand: AppointmentDemand) -> AppointmentDemand:
        normalized = self._normalize_demand(demand)
        key = normalized.appointment_id.casefold()
        if key in self._demands:
            raise ValueError(f"duplicate appointment demand: {normalized.appointment_id}")
        self._demands[key] = normalized
        return normalized

    def _load_hold(self, hold: ResourceHold) -> None:
        normalized = self._normalize_hold(hold)
        key = normalized.hold_id.casefold()
        if key in self._holds:
            raise ValueError(f"duplicate resource hold: {normalized.hold_id}")
        demand = self._demand(normalized.appointment_id)
        resource = self._resource(normalized.resource_id)
        requirement = self._requirement(demand, normalized.requirement_id)
        if resource.kind is not requirement.kind:
            raise ValueError("held resource kind does not satisfy requirement")
        self._holds[key] = normalized

    def plan(self, appointment_id: str, as_of: datetime) -> AppointmentResourcePlan:
        demand = self._demand(appointment_id)
        now = _instant(as_of, "as of")
        requirement_plans: list[RequirementPlan] = []
        blockers: list[str] = []
        reserved: set[str] = set()
        for requirement in demand.requirements:
            existing = self._live_holds(demand.appointment_id, requirement.requirement_id, now)
            selected = [hold.resource_id for hold in existing]
            reserved.update(resource_id.casefold() for resource_id in selected)
            needed = max(0, requirement.quantity - len(selected))
            for resource in self._eligible_resources(demand, requirement, now):
                if needed == 0:
                    break
                if resource.resource_id.casefold() in reserved:
                    continue
                selected.append(resource.resource_id)
                reserved.add(resource.resource_id.casefold())
                needed -= 1
            requirement_plans.append(RequirementPlan(requirement.requirement_id, tuple(selected), needed))
            if needed:
                blockers.append(f"{requirement.requirement_id} is short by {needed}")
        if demand.starts_at <= now:
            blockers.append("appointment resource window has started")
        return AppointmentResourcePlan(demand.appointment_id, tuple(requirement_plans), not blockers, tuple(blockers))

    def hold(self, appointment_id: str, as_of: datetime, hold_minutes: int = 15) -> tuple[ResourceHold, ...]:
        now = _instant(as_of, "as of")
        duration = _positive(hold_minutes, "hold minutes")
        plan = self.plan(appointment_id, now)
        if not plan.ready:
            raise ValueError("appointment resources cannot be held atomically")
        created: list[ResourceHold] = []
        for requirement in plan.requirements:
            for resource_id in requirement.resource_ids:
                if any(
                    existing.resource_id.casefold() == resource_id.casefold()
                    for existing in self._live_holds(appointment_id, requirement.requirement_id, now)
                ):
                    continue
                hold_id = f"hold:{appointment_id}:{requirement.requirement_id}:{resource_id}"
                hold = ResourceHold(
                    hold_id=hold_id,
                    appointment_id=appointment_id,
                    requirement_id=requirement.requirement_id,
                    resource_id=resource_id,
                    held_at=now,
                    expires_at=now + timedelta(minutes=duration),
                    state=HoldState.HELD,
                )
                key = hold.hold_id.casefold()
                if key in self._holds:
                    raise ValueError(f"duplicate resource hold: {hold.hold_id}")
                self._holds[key] = hold
                created.append(hold)
        return tuple(created)

    def confirm(self, appointment_id: str, confirmed_at: datetime) -> tuple[ResourceHold, ...]:
        demand = self._demand(appointment_id)
        confirmed = _instant(confirmed_at, "confirmed at")
        live = self._live_holds(demand.appointment_id, None, confirmed)
        readiness = self._holds_satisfy(demand, live)
        if not readiness:
            raise ValueError("appointment does not have a complete live hold set")
        updated: list[ResourceHold] = []
        for hold in live:
            if hold.state is HoldState.CONFIRMED:
                updated.append(hold)
                continue
            if confirmed > hold.expires_at:
                raise ValueError("appointment resource hold has expired")
            value = replace(hold, state=HoldState.CONFIRMED, confirmed_at=confirmed)
            self._holds[hold.hold_id.casefold()] = value
            updated.append(value)
        updated.sort(key=lambda item: (item.requirement_id, item.resource_id))
        return tuple(updated)

    def release(self, appointment_id: str, released_at: datetime) -> tuple[ResourceHold, ...]:
        demand = self._demand(appointment_id)
        released = _instant(released_at, "released at")
        updated: list[ResourceHold] = []
        for key, hold in self._holds.items():
            if hold.appointment_id.casefold() != demand.appointment_id.casefold():
                continue
            if hold.state not in {HoldState.HELD, HoldState.CONFIRMED}:
                continue
            if released < hold.held_at:
                raise ValueError("release cannot predate hold")
            value = replace(hold, state=HoldState.RELEASED, released_at=released)
            self._holds[key] = value
            updated.append(value)
        updated.sort(key=lambda item: item.hold_id)
        return tuple(updated)

    def expire(self, as_of: datetime) -> tuple[ResourceHold, ...]:
        now = _instant(as_of, "as of")
        expired: list[ResourceHold] = []
        for key, hold in self._holds.items():
            if hold.state is not HoldState.HELD or hold.expires_at >= now:
                continue
            value = replace(hold, state=HoldState.EXPIRED)
            self._holds[key] = value
            expired.append(value)
        expired.sort(key=lambda item: (item.expires_at, item.hold_id))
        return tuple(expired)

    def conflicts(self, resource_id: str, starts_at: datetime, ends_at: datetime) -> tuple[ResourceHold, ...]:
        resource = self._resource(resource_id)
        starts = _instant(starts_at, "conflict start")
        ends = _instant(ends_at, "conflict end")
        if ends <= starts:
            raise ValueError("conflict end must follow start")
        conflicts: list[ResourceHold] = []
        for hold in self._holds.values():
            if hold.resource_id.casefold() != resource.resource_id.casefold():
                continue
            if hold.state not in {HoldState.HELD, HoldState.CONFIRMED}:
                continue
            demand = self._demand(hold.appointment_id)
            if starts < demand.ends_at and demand.starts_at < ends:
                conflicts.append(hold)
        conflicts.sort(key=lambda item: (self._demand(item.appointment_id).starts_at, item.hold_id))
        return tuple(conflicts)

    def _eligible_resources(
        self,
        demand: AppointmentDemand,
        requirement: ResourceRequirement,
        as_of: datetime,
    ) -> tuple[AppointmentResource, ...]:
        eligible: list[AppointmentResource] = []
        for resource in self._resources.values():
            if not resource.active or resource.kind is not requirement.kind or resource.site_id != demand.site_id:
                continue
            if resource.available_from > demand.starts_at or resource.available_until < demand.ends_at:
                continue
            if not set(requirement.capabilities) <= set(resource.capabilities):
                continue
            conflicts = self.conflicts(resource.resource_id, demand.starts_at, demand.ends_at)
            if any(hold.appointment_id.casefold() != demand.appointment_id.casefold() for hold in conflicts):
                continue
            eligible.append(resource)
        eligible.sort(key=lambda item: (len(item.capabilities), item.resource_id))
        return tuple(eligible)

    def _live_holds(
        self,
        appointment_id: str,
        requirement_id: str | None,
        as_of: datetime,
    ) -> tuple[ResourceHold, ...]:
        result = [
            hold
            for hold in self._holds.values()
            if hold.appointment_id.casefold() == appointment_id.casefold()
            and (requirement_id is None or hold.requirement_id.casefold() == requirement_id.casefold())
            and (hold.state is HoldState.CONFIRMED or (hold.state is HoldState.HELD and hold.expires_at >= as_of))
        ]
        result.sort(key=lambda item: (item.requirement_id, item.resource_id))
        return tuple(result)

    def _holds_satisfy(self, demand: AppointmentDemand, holds: tuple[ResourceHold, ...]) -> bool:
        for requirement in demand.requirements:
            count = sum(hold.requirement_id.casefold() == requirement.requirement_id.casefold() for hold in holds)
            if count < requirement.quantity:
                return False
        return True

    def _demand(self, appointment_id: str) -> AppointmentDemand:
        normalized = _text(appointment_id, "appointment id")
        try:
            return self._demands[normalized.casefold()]
        except KeyError as exc:
            raise KeyError(f"unknown appointment demand: {normalized}") from exc

    def _resource(self, resource_id: str) -> AppointmentResource:
        normalized = _text(resource_id, "resource id")
        try:
            return self._resources[normalized.casefold()]
        except KeyError as exc:
            raise KeyError(f"unknown appointment resource: {normalized}") from exc

    def _requirement(self, demand: AppointmentDemand, requirement_id: str) -> ResourceRequirement:
        normalized = _text(requirement_id, "requirement id")
        for requirement in demand.requirements:
            if requirement.requirement_id.casefold() == normalized.casefold():
                return requirement
        raise KeyError(f"unknown appointment requirement: {normalized}")
