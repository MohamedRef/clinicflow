"""Control release of quarantined non-clinical clinic inventory."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class QuarantinedInventoryLot:
    lot_id: str
    quarantined_day: int
    required_check_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InventoryReleaseCheck:
    lot_id: str
    check_id: str
    completed_day: int
    passed: bool


@dataclass(frozen=True, slots=True)
class InventoryQuarantineFinding:
    lot_id: str
    age_days: int
    missing_check_ids: tuple[str, ...]
    failed_check_ids: tuple[str, ...]
    releasable: bool


def assess_inventory_quarantine(
    lots: list[QuarantinedInventoryLot], checks: list[InventoryReleaseCheck], now_day: int
) -> list[InventoryQuarantineFinding]:
    """Require every declared check to pass after quarantine began."""
    if now_day < 0:
        raise DomainError("quarantine assessment day cannot be negative")
    by_lot: dict[str, QuarantinedInventoryLot] = {}
    for lot in lots:
        lot_id = clean_code(lot.lot_id, "quarantine lot id")
        required = tuple(clean_code(item, "release check id") for item in lot.required_check_ids)
        if lot_id in by_lot or not required or len(set(required)) != len(required):
            raise DomainError("quarantine lots and required checks must be unique and non-empty")
        if lot.quarantined_day < 0 or lot.quarantined_day > now_day:
            raise DomainError("quarantine day cannot be in the future")
        by_lot[lot_id] = QuarantinedInventoryLot(lot_id, lot.quarantined_day, required)

    observed: dict[tuple[str, str], InventoryReleaseCheck] = {}
    for check in checks:
        lot_id = clean_code(check.lot_id, "release check lot id")
        check_id = clean_code(check.check_id, "release check id")
        current_lot = by_lot.get(lot_id)
        key = (lot_id, check_id)
        if current_lot is None or check_id not in current_lot.required_check_ids or key in observed:
            raise DomainError("release checks must be unique and declared by their lot")
        if check.completed_day < current_lot.quarantined_day or check.completed_day > now_day:
            raise DomainError("release check completion is outside the quarantine window")
        if not isinstance(check.passed, bool):
            raise DomainError("release check outcome must be a boolean")
        observed[key] = check

    findings: list[InventoryQuarantineFinding] = []
    for lot_id, lot in by_lot.items():
        missing = tuple(sorted(check_id for check_id in lot.required_check_ids if (lot_id, check_id) not in observed))
        failed = tuple(
            sorted(
                check_id
                for check_id in lot.required_check_ids
                if not observed.get((lot_id, check_id), InventoryReleaseCheck(lot_id, check_id, 0, True)).passed
            )
        )
        findings.append(
            InventoryQuarantineFinding(
                lot_id, now_day - lot.quarantined_day, missing, failed, not missing and not failed
            )
        )
    return sorted(findings, key=lambda item: (item.releasable, -item.age_days, item.lot_id))
