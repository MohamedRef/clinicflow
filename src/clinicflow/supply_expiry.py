"""FEFO allocation of expiring clinic supplies to scheduled demand."""

from dataclasses import dataclass
from datetime import datetime

from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class ExpiringSupplyBatch:
    batch_id: str
    item_id: str
    quantity: int
    expires_at: str
    quarantined: bool = False


@dataclass(frozen=True, slots=True)
class ScheduledSupplyDemand:
    demand_id: str
    item_id: str
    quantity: int
    needed_at: str
    priority: int


@dataclass(frozen=True, slots=True)
class ExpiryAllocation:
    demand_id: str
    item_id: str
    allocations: tuple[tuple[str, int], ...]
    shortage: int
    fulfilled: bool


def allocate_expiring_supplies(
    batches: list[ExpiringSupplyBatch], demands: list[ScheduledSupplyDemand]
) -> list[ExpiryAllocation]:
    """Allocate usable stock by earliest expiry without mutating caller records."""
    batch_rows: list[tuple[ExpiringSupplyBatch, datetime]] = []
    batch_ids: set[str] = set()
    for batch in batches:
        batch_id = clean_code(batch.batch_id, "supply batch id")
        if batch_id in batch_ids:
            raise DomainError(f"duplicate supply batch id: {batch_id}")
        batch_ids.add(batch_id)
        item_id = clean_code(batch.item_id, "supply item id")
        if isinstance(batch.quantity, bool) or not isinstance(batch.quantity, int) or batch.quantity < 0:
            raise DomainError("supply batch quantity must be a non-negative integer")
        expiry = parse_time(batch.expires_at, "expires_at")
        batch_rows.append(
            (ExpiringSupplyBatch(batch_id, item_id, batch.quantity, batch.expires_at, batch.quarantined), expiry)
        )
    demand_rows: list[tuple[ScheduledSupplyDemand, datetime]] = []
    demand_ids: set[str] = set()
    for demand in demands:
        demand_id = clean_code(demand.demand_id, "supply demand id")
        if demand_id in demand_ids:
            raise DomainError(f"duplicate supply demand id: {demand_id}")
        demand_ids.add(demand_id)
        item_id = clean_code(demand.item_id, "supply demand item id")
        if isinstance(demand.quantity, bool) or not isinstance(demand.quantity, int) or demand.quantity < 1:
            raise DomainError("supply demand quantity must be a positive integer")
        if isinstance(demand.priority, bool) or not isinstance(demand.priority, int) or not 1 <= demand.priority <= 5:
            raise DomainError("supply demand priority must be from 1 through 5")
        needed_at = parse_time(demand.needed_at, "needed_at")
        demand_rows.append(
            (ScheduledSupplyDemand(demand_id, item_id, demand.quantity, demand.needed_at, demand.priority), needed_at)
        )
    remaining = {batch.batch_id: batch.quantity for batch, _ in batch_rows}
    results: list[ExpiryAllocation] = []
    for demand, needed_at in sorted(demand_rows, key=lambda row: (row[1], -row[0].priority, row[0].demand_id)):
        required = demand.quantity
        allocations: list[tuple[str, int]] = []
        candidates = sorted(
            (
                (batch, expiry)
                for batch, expiry in batch_rows
                if batch.item_id == demand.item_id
                and not batch.quarantined
                and expiry > needed_at
                and remaining[batch.batch_id] > 0
            ),
            key=lambda row: (row[1], row[0].batch_id),
        )
        for batch, _ in candidates:
            if required == 0:
                break
            quantity = min(required, remaining[batch.batch_id])
            remaining[batch.batch_id] -= quantity
            required -= quantity
            allocations.append((batch.batch_id, quantity))
        results.append(ExpiryAllocation(demand.demand_id, demand.item_id, tuple(allocations), required, required == 0))
    return results
