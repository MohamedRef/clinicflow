"""Appointment impact and replacement planning for recalled supply lots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .inventory_allocation import InventoryBatch
from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class ScheduledBatchAllocation:
    appointment_id: str
    sku: str
    lot_id: str
    quantity: int
    needed_at: str
    priority: int


@dataclass(frozen=True, slots=True)
class RecallReplacement:
    appointment_id: str
    sku: str
    recalled_lot_id: str
    replacement_lot_id: str
    quantity: int


@dataclass(frozen=True, slots=True)
class RecallShortage:
    appointment_id: str
    sku: str
    recalled_lot_id: str
    missing_quantity: int


def replace_recalled_allocations(
    allocations: list[ScheduledBatchAllocation],
    recalled_lot_ids: set[str],
    replacement_batches: list[InventoryBatch],
) -> tuple[list[RecallReplacement], list[RecallShortage]]:
    """Reallocate affected appointments by urgency without using recalled or expired lots."""
    recalled = {clean_code(lot_id, "recalled lot id") for lot_id in recalled_lot_ids}
    if not recalled:
        raise DomainError("at least one recalled lot id is required")

    remaining: dict[str, int] = {}
    normalized_batches: list[tuple[InventoryBatch, datetime]] = []
    for batch in replacement_batches:
        lot_id = clean_code(batch.lot_id, "replacement lot id")
        sku = clean_code(batch.sku, "replacement sku")
        if lot_id in remaining:
            raise DomainError(f"duplicate replacement lot id: {lot_id}")
        if lot_id in recalled:
            raise DomainError(f"recalled lot cannot be a replacement: {lot_id}")
        if isinstance(batch.quantity, bool) or not isinstance(batch.quantity, int) or batch.quantity < 0:
            raise DomainError("replacement quantity must be a non-negative integer")
        remaining[lot_id] = batch.quantity
        normalized_batches.append(
            (InventoryBatch(lot_id, sku, batch.quantity, batch.expires_at), parse_time(batch.expires_at, "expires_at"))
        )
    normalized_batches.sort(key=lambda item: (item[1], item[0].lot_id))

    seen: set[tuple[str, str, str]] = set()
    impacted: list[tuple[ScheduledBatchAllocation, datetime]] = []
    for allocation in allocations:
        appointment_id = clean_code(allocation.appointment_id, "appointment id")
        sku = clean_code(allocation.sku, "sku")
        lot_id = clean_code(allocation.lot_id, "allocated lot id")
        key = (appointment_id, sku, lot_id)
        if key in seen:
            raise DomainError("duplicate scheduled batch allocation")
        seen.add(key)
        if isinstance(allocation.quantity, bool) or not isinstance(allocation.quantity, int) or allocation.quantity < 1:
            raise DomainError("allocated quantity must be a positive integer")
        if (
            isinstance(allocation.priority, bool)
            or not isinstance(allocation.priority, int)
            or not 1 <= allocation.priority <= 5
        ):
            raise DomainError("recall priority must be an integer from 1 through 5")
        needed_at = parse_time(allocation.needed_at, "needed_at")
        if lot_id in recalled:
            impacted.append(
                (
                    ScheduledBatchAllocation(
                        appointment_id, sku, lot_id, allocation.quantity, allocation.needed_at, allocation.priority
                    ),
                    needed_at,
                )
            )

    replacements: list[RecallReplacement] = []
    shortages: list[RecallShortage] = []
    for allocation, needed_at in sorted(
        impacted,
        key=lambda item: (-item[0].priority, item[1], item[0].appointment_id, item[0].sku),
    ):
        missing = allocation.quantity
        for batch, expires_at in normalized_batches:
            if batch.sku != allocation.sku or expires_at <= needed_at or remaining[batch.lot_id] == 0:
                continue
            granted = min(missing, remaining[batch.lot_id])
            remaining[batch.lot_id] -= granted
            missing -= granted
            replacements.append(
                RecallReplacement(
                    allocation.appointment_id,
                    allocation.sku,
                    allocation.lot_id,
                    batch.lot_id,
                    granted,
                )
            )
            if missing == 0:
                break
        if missing:
            shortages.append(RecallShortage(allocation.appointment_id, allocation.sku, allocation.lot_id, missing))
    return replacements, shortages
