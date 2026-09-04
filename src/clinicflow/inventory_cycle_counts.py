"""Reconcile stockroom cycle counts against ledger positions."""

from __future__ import annotations

from dataclasses import dataclass

from clinicflow.models import DomainError


@dataclass(frozen=True, slots=True)
class InventoryLedgerPosition:
    item_id: str
    location: str
    expected_units: int
    unit_value_cents: int
    controlled_item: bool = False


@dataclass(frozen=True, slots=True)
class InventoryCycleCount:
    item_id: str
    location: str
    counted_units: int
    witness_present: bool


@dataclass(frozen=True, slots=True)
class CycleCountFinding:
    item_id: str
    location: str
    variance_units: int
    variance_value_cents: int
    blockers: tuple[str, ...]
    action: str


def reconcile_cycle_counts(
    positions: list[InventoryLedgerPosition], counts: list[InventoryCycleCount], *, material_variance_cents: int
) -> list[CycleCountFinding]:
    """Detect missing counts, value variance, and unwitnessed controlled counts."""
    if material_variance_cents < 0:
        raise DomainError("cycle count material variance cannot be negative")
    configured: dict[tuple[str, str], InventoryLedgerPosition] = {}
    for position in positions:
        item = _text(position.item_id, "cycle count item", maximum=120)
        location = _text(position.location, "cycle count location", maximum=120)
        key = (item.casefold(), location.casefold())
        if key in configured or position.expected_units < 0 or position.unit_value_cents < 0:
            raise DomainError(f"invalid or duplicate inventory ledger position {item}/{location}")
        configured[key] = InventoryLedgerPosition(
            item, location, position.expected_units, position.unit_value_cents, position.controlled_item
        )
    received: dict[tuple[str, str], InventoryCycleCount] = {}
    for count in counts:
        item = _text(count.item_id, "cycle count observation item", maximum=120)
        location = _text(count.location, "cycle count observation location", maximum=120)
        key = (item.casefold(), location.casefold())
        if key not in configured or key in received or count.counted_units < 0:
            raise DomainError(f"invalid or duplicate inventory cycle count {item}/{location}")
        received[key] = InventoryCycleCount(item, location, count.counted_units, count.witness_present)
    findings: list[CycleCountFinding] = []
    for key, position in configured.items():
        observed = received.get(key)
        variance = (observed.counted_units if observed else 0) - position.expected_units
        value = variance * position.unit_value_cents
        blockers: list[str] = []
        if observed is None:
            blockers.append("count_missing")
        if observed and position.controlled_item and not observed.witness_present:
            blockers.append("witness_missing")
        if abs(value) > material_variance_cents:
            blockers.append("material_variance")
        action = "investigate" if blockers else "reconciled"
        findings.append(
            CycleCountFinding(position.item_id, position.location, variance, value, tuple(blockers), action)
        )
    return sorted(findings, key=lambda row: (row.action == "reconciled", -abs(row.variance_value_cents), row.item_id))


def _text(value: str, field: str, *, maximum: int) -> str:
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > maximum:
        raise DomainError(f"{field} is invalid")
    return normalized
