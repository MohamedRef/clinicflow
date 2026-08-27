"""Expiry-aware inventory allocation for scheduled clinic appointments."""

from dataclasses import dataclass
from datetime import datetime

from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class InventoryBatch:
    lot_id: str
    sku: str
    quantity: int
    expires_at: str


@dataclass(frozen=True, slots=True)
class SupplyDemand:
    appointment_id: str
    sku: str
    quantity: int
    needed_at: str


@dataclass(frozen=True, slots=True)
class BatchAllocation:
    appointment_id: str
    sku: str
    lot_id: str
    quantity: int


@dataclass(frozen=True, slots=True)
class SupplyShortage:
    appointment_id: str
    sku: str
    missing_quantity: int


def allocate_inventory(
    demands: list[SupplyDemand], batches: list[InventoryBatch]
) -> tuple[list[BatchAllocation], list[SupplyShortage]]:
    """Allocate earliest-expiring valid batches to chronological demand."""
    remaining: dict[str, int] = {}
    normalized_batches: list[tuple[InventoryBatch, datetime]] = []
    for batch in batches:
        lot_id = clean_code(batch.lot_id, "lot id")
        sku = clean_code(batch.sku, "sku")
        if lot_id in remaining:
            raise DomainError(f"duplicate inventory lot id: {lot_id}")
        if isinstance(batch.quantity, bool) or not isinstance(batch.quantity, int) or batch.quantity < 0:
            raise DomainError("batch quantity must be a non-negative integer")
        expires = parse_time(batch.expires_at, "expires_at")
        remaining[lot_id] = batch.quantity
        normalized_batches.append((InventoryBatch(lot_id, sku, batch.quantity, batch.expires_at), expires))
    normalized_batches.sort(key=lambda item: (item[1], item[0].lot_id))

    seen_demands: set[tuple[str, str]] = set()
    normalized_demands: list[tuple[SupplyDemand, datetime]] = []
    for demand in demands:
        appointment_id = clean_code(demand.appointment_id, "appointment id")
        sku = clean_code(demand.sku, "sku")
        key = (appointment_id, sku)
        if key in seen_demands:
            raise DomainError("duplicate appointment inventory demand")
        seen_demands.add(key)
        if isinstance(demand.quantity, bool) or not isinstance(demand.quantity, int) or demand.quantity < 1:
            raise DomainError("demand quantity must be a positive integer")
        needed = parse_time(demand.needed_at, "needed_at")
        normalized_demands.append((SupplyDemand(appointment_id, sku, demand.quantity, demand.needed_at), needed))
    normalized_demands.sort(key=lambda item: (item[1], item[0].appointment_id, item[0].sku))

    allocations: list[BatchAllocation] = []
    shortages: list[SupplyShortage] = []
    for demand, needed in normalized_demands:
        missing = demand.quantity
        for batch, expires in normalized_batches:
            if batch.sku != demand.sku or expires <= needed or remaining[batch.lot_id] == 0:
                continue
            granted = min(missing, remaining[batch.lot_id])
            remaining[batch.lot_id] -= granted
            missing -= granted
            allocations.append(BatchAllocation(demand.appointment_id, demand.sku, batch.lot_id, granted))
            if missing == 0:
                break
        if missing:
            shortages.append(SupplyShortage(demand.appointment_id, demand.sku, missing))
    return allocations, shortages
