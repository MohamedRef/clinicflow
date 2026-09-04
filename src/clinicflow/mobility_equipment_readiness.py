"""Assess non-clinical mobility equipment available for appointments."""

from dataclasses import dataclass
from datetime import UTC, datetime

from clinicflow.models import DomainError, clean_text


@dataclass(frozen=True, slots=True)
class MobilityEquipmentCheck:
    equipment_id: str
    kind: str
    inspected_at: datetime
    brakes_operational: bool
    safety_belt_present: bool
    clean: bool
    reserved_for: str | None = None


@dataclass(frozen=True, slots=True)
class MobilityEquipmentFinding:
    equipment_id: str
    kind: str
    defects: tuple[str, ...]
    state: str


def assess_mobility_equipment(
    checks: list[MobilityEquipmentCheck],
    *,
    reviewed_at: datetime,
    maximum_inspection_age_hours: int = 24,
) -> list[MobilityEquipmentFinding]:
    """Return quarantine, refresh, reserved, and ready equipment."""
    review = _aware(reviewed_at, "mobility equipment review")
    if maximum_inspection_age_hours < 1:
        raise DomainError("mobility inspection age is invalid")
    seen: set[str] = set()
    findings: list[MobilityEquipmentFinding] = []
    for check in checks:
        equipment_id = clean_text(check.equipment_id, "mobility equipment", 120)
        kind = clean_text(check.kind, "mobility equipment kind", 80).casefold()
        key = equipment_id.casefold()
        if key in seen:
            raise DomainError("duplicate mobility equipment")
        seen.add(key)
        inspected = _aware(check.inspected_at, "mobility inspection")
        if inspected > review:
            raise DomainError("mobility inspection cannot be in the future")
        age_hours = int((review - inspected).total_seconds() // 3600)
        defects: list[str] = []
        if not check.brakes_operational:
            defects.append("brake_fault")
        if not check.safety_belt_present:
            defects.append("belt_missing")
        if not check.clean:
            defects.append("cleaning_required")
        if age_hours > maximum_inspection_age_hours:
            defects.append("inspection_stale")
        if "brake_fault" in defects or "belt_missing" in defects:
            state = "quarantine"
        elif defects:
            state = "refresh"
        elif check.reserved_for and check.reserved_for.strip():
            state = "reserved"
        else:
            state = "ready"
        findings.append(MobilityEquipmentFinding(equipment_id, kind, tuple(defects), state))
    order = {"quarantine": 0, "refresh": 1, "reserved": 2, "ready": 3}
    return sorted(findings, key=lambda row: (order[row.state], row.kind, row.equipment_id))


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)
