"""Allocate usable cleaning supplies to planned room turnovers."""

from dataclasses import dataclass
from datetime import date

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class CleaningSupplyBatch:
    batch_id: str
    supply_type: str
    units: int
    expires_on: str


@dataclass(frozen=True, slots=True)
class CleaningSupplyDemand:
    turnover_id: str
    supply_type: str
    units: int
    needed_on: str


@dataclass(frozen=True, slots=True)
class CleaningSupplyAllocation:
    turnover_id: str
    batch_id: str
    units: int


@dataclass(frozen=True, slots=True)
class CleaningSupplyShortage:
    turnover_id: str
    supply_type: str
    missing_units: int


def _day(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise DomainError(f"{field} must be an ISO date") from error


def allocate_cleaning_supplies(
    batches: list[CleaningSupplyBatch], demands: list[CleaningSupplyDemand]
) -> tuple[list[CleaningSupplyAllocation], list[CleaningSupplyShortage]]:
    """Allocate earliest-expiring eligible stock without using expired batches."""
    available: dict[str, tuple[str, int, date]] = {}
    by_type: dict[str, list[str]] = {}
    for batch in batches:
        batch_id = clean_code(batch.batch_id, "cleaning batch id")
        supply_type = clean_code(batch.supply_type, "cleaning supply type").lower()
        if batch_id in available:
            raise DomainError(f"duplicate cleaning supply batch: {batch_id}")
        if not isinstance(batch.units, int) or isinstance(batch.units, bool) or batch.units < 1:
            raise DomainError("cleaning supply units must be a positive integer")
        available[batch_id] = (supply_type, batch.units, _day(batch.expires_on, "cleaning supply expiry"))
        by_type.setdefault(supply_type, []).append(batch_id)
    seen_demands: set[str] = set()
    allocations: list[CleaningSupplyAllocation] = []
    shortages: list[CleaningSupplyShortage] = []
    for demand in sorted(demands, key=lambda item: (_day(item.needed_on, "cleaning need date"), item.turnover_id)):
        turnover_id = clean_code(demand.turnover_id, "cleaning turnover id")
        supply_type = clean_code(demand.supply_type, "cleaning demand type").lower()
        if turnover_id in seen_demands:
            raise DomainError(f"duplicate cleaning supply demand: {turnover_id}")
        if not isinstance(demand.units, int) or isinstance(demand.units, bool) or demand.units < 1:
            raise DomainError("cleaning demand units must be a positive integer")
        seen_demands.add(turnover_id)
        needed_on = _day(demand.needed_on, "cleaning need date")
        remaining = demand.units
        candidates = sorted(by_type.get(supply_type, []), key=lambda batch_id: (available[batch_id][2], batch_id))
        for batch_id in candidates:
            batch_type, units, expires_on = available[batch_id]
            if remaining == 0:
                break
            if expires_on < needed_on or units == 0:
                continue
            allocated = min(remaining, units)
            allocations.append(CleaningSupplyAllocation(turnover_id, batch_id, allocated))
            available[batch_id] = (batch_type, units - allocated, expires_on)
            remaining -= allocated
        if remaining:
            shortages.append(CleaningSupplyShortage(turnover_id, supply_type, remaining))
    return allocations, shortages
