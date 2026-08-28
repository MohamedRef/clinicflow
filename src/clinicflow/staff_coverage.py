"""Qualification-aware replacement coverage for staff absences."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import DomainError, clean_code, clean_codes, parse_time


@dataclass(frozen=True, slots=True)
class CoverageDemand:
    appointment_id: str
    absent_staff_id: str
    starts_at: str
    ends_at: str
    required_qualifications: set[str]
    priority: int


@dataclass(frozen=True, slots=True)
class SubstituteStaff:
    staff_id: str
    qualifications: set[str]
    available_from: str
    available_until: str
    maximum_assignments: int


@dataclass(frozen=True, slots=True)
class CoverageAssignment:
    appointment_id: str
    substitute_staff_id: str | None
    assigned: bool
    reason: str


def assign_staff_coverage(
    demands: list[CoverageDemand], substitutes: list[SubstituteStaff]
) -> list[CoverageAssignment]:
    """Assign substitutes without qualification, availability, or overlap conflicts."""
    normalized_substitutes: dict[str, tuple[SubstituteStaff, datetime, datetime]] = {}
    for substitute in substitutes:
        staff_id = clean_code(substitute.staff_id, "substitute staff id")
        if staff_id in normalized_substitutes:
            raise DomainError(f"duplicate substitute staff id: {staff_id}")
        available_from = parse_time(substitute.available_from, "available_from")
        available_until = parse_time(substitute.available_until, "available_until")
        if available_until <= available_from:
            raise DomainError("substitute availability must have a positive duration")
        if (
            isinstance(substitute.maximum_assignments, bool)
            or not isinstance(substitute.maximum_assignments, int)
            or not 1 <= substitute.maximum_assignments <= 20
        ):
            raise DomainError("maximum_assignments must be an integer from 1 through 20")
        normalized_substitutes[staff_id] = (
            SubstituteStaff(
                staff_id,
                clean_codes(substitute.qualifications, "substitute qualification"),
                substitute.available_from,
                substitute.available_until,
                substitute.maximum_assignments,
            ),
            available_from,
            available_until,
        )

    seen_demands: set[str] = set()
    normalized_demands: list[tuple[CoverageDemand, datetime, datetime]] = []
    for demand in demands:
        appointment_id = clean_code(demand.appointment_id, "coverage appointment id")
        if appointment_id in seen_demands:
            raise DomainError(f"duplicate coverage appointment id: {appointment_id}")
        seen_demands.add(appointment_id)
        starts_at = parse_time(demand.starts_at, "starts_at")
        ends_at = parse_time(demand.ends_at, "ends_at")
        if ends_at <= starts_at:
            raise DomainError("coverage ends_at must follow starts_at")
        if isinstance(demand.priority, bool) or not isinstance(demand.priority, int) or not 1 <= demand.priority <= 5:
            raise DomainError("coverage priority must be an integer from 1 through 5")
        normalized_demands.append(
            (
                CoverageDemand(
                    appointment_id,
                    clean_code(demand.absent_staff_id, "absent staff id"),
                    demand.starts_at,
                    demand.ends_at,
                    clean_codes(demand.required_qualifications, "required qualification"),
                    demand.priority,
                ),
                starts_at,
                ends_at,
            )
        )

    allocated_windows: dict[str, list[tuple[datetime, datetime]]] = {
        staff_id: [] for staff_id in normalized_substitutes
    }
    assignments: list[CoverageAssignment] = []
    for demand, starts_at, ends_at in sorted(
        normalized_demands,
        key=lambda item: (-item[0].priority, item[1], item[0].appointment_id),
    ):
        eligible: list[str] = []
        for staff_id, (substitute, available_from, available_until) in normalized_substitutes.items():
            windows = allocated_windows[staff_id]
            if staff_id == demand.absent_staff_id:
                continue
            if not demand.required_qualifications <= substitute.qualifications:
                continue
            if starts_at < available_from or ends_at > available_until:
                continue
            if len(windows) >= substitute.maximum_assignments:
                continue
            if any(starts_at < assigned_end and assigned_start < ends_at for assigned_start, assigned_end in windows):
                continue
            eligible.append(staff_id)
        if not eligible:
            assignments.append(
                CoverageAssignment(demand.appointment_id, None, False, "no qualified available substitute")
            )
            continue
        selected = sorted(eligible, key=lambda staff_id: (len(allocated_windows[staff_id]), staff_id))[0]
        allocated_windows[selected].append((starts_at, ends_at))
        assignments.append(CoverageAssignment(demand.appointment_id, selected, True, "coverage assigned"))
    return assignments
