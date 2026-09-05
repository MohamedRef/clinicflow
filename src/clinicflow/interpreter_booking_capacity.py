"""Deterministic interpreter booking capacity allocation."""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InterpreterBookingCapacityResource:
    resource_id: str
    group: str
    available_units: int


@dataclass(frozen=True, slots=True)
class InterpreterBookingCapacityDemand:
    demand_id: str
    group: str
    required_units: int
    priority: int


@dataclass(frozen=True, slots=True)
class InterpreterBookingCapacityAllocation:
    resource_id: str
    units: int


@dataclass(frozen=True, slots=True)
class InterpreterBookingCapacityDecision:
    demand_id: str
    allocations: tuple[InterpreterBookingCapacityAllocation, ...]
    shortfall_units: int


def _required(value: str, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"interpreter booking {field} is required")
    return normalized


def _positive(value: int, field: str) -> int:
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"interpreter booking {field} must be positive")
    return value


def allocate_interpreter_booking_capacity(
    resources: Iterable[InterpreterBookingCapacityResource],
    demands: Iterable[InterpreterBookingCapacityDemand],
) -> tuple[InterpreterBookingCapacityDecision, ...]:
    """Allocate capacity by priority without crossing operational groups."""
    resource_ids: set[str] = set()
    normalized_resources: list[InterpreterBookingCapacityResource] = []
    for resource in resources:
        resource_id = _required(resource.resource_id, "resource")
        identity = resource_id.casefold()
        if identity in resource_ids:
            raise ValueError(f"duplicate interpreter booking resource: {resource_id}")
        resource_ids.add(identity)
        normalized_resources.append(
            InterpreterBookingCapacityResource(
                resource_id=resource_id,
                group=_required(resource.group, "resource group").casefold(),
                available_units=_positive(resource.available_units, "available units"),
            )
        )
    normalized_resources.sort(key=lambda item: item.resource_id)
    remaining = {resource.resource_id: resource.available_units for resource in normalized_resources}

    demand_ids: set[str] = set()
    normalized_demands: list[InterpreterBookingCapacityDemand] = []
    for demand in demands:
        demand_id = _required(demand.demand_id, "demand")
        identity = demand_id.casefold()
        if identity in demand_ids:
            raise ValueError(f"duplicate interpreter booking demand: {demand_id}")
        demand_ids.add(identity)
        normalized_demands.append(
            InterpreterBookingCapacityDemand(
                demand_id=demand_id,
                group=_required(demand.group, "demand group").casefold(),
                required_units=_positive(demand.required_units, "required units"),
                priority=_positive(demand.priority, "priority"),
            )
        )
    normalized_demands.sort(key=lambda item: (-item.priority, -item.required_units, item.demand_id))

    decisions: list[InterpreterBookingCapacityDecision] = []
    for demand in normalized_demands:
        needed = demand.required_units
        allocations: list[InterpreterBookingCapacityAllocation] = []
        for resource in normalized_resources:
            if resource.group != demand.group or needed == 0:
                continue
            units = min(remaining[resource.resource_id], needed)
            if units == 0:
                continue
            allocations.append(InterpreterBookingCapacityAllocation(resource_id=resource.resource_id, units=units))
            remaining[resource.resource_id] -= units
            needed -= units
        decisions.append(
            InterpreterBookingCapacityDecision(
                demand_id=demand.demand_id,
                allocations=tuple(allocations),
                shortfall_units=needed,
            )
        )
    return tuple(decisions)
