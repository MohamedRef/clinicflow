"""Allocate non-clinical language support to appointment arrival windows."""

from dataclasses import dataclass
from datetime import datetime

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class LanguageSupportDemand:
    appointment_id: str
    language: str
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True, slots=True)
class LanguageSupportShift:
    staff_id: str
    languages: frozenset[str]
    starts_at: datetime
    ends_at: datetime
    maximum_appointments: int


@dataclass(frozen=True, slots=True)
class LanguageSupportAssignment:
    appointment_id: str
    staff_id: str | None
    reason: str | None


def allocate_language_support(
    demands: list[LanguageSupportDemand], shifts: list[LanguageSupportShift]
) -> list[LanguageSupportAssignment]:
    """Assign language support deterministically while respecting shift capacity."""
    demand_ids: set[str] = set()
    normalized_demands: list[tuple[LanguageSupportDemand, str, str]] = []
    for demand in demands:
        appointment_id = clean_code(demand.appointment_id, "language support appointment id")
        language = clean_code(demand.language, "language support language").lower()
        if appointment_id in demand_ids:
            raise DomainError(f"duplicate language support demand: {appointment_id}")
        if demand.ends_at <= demand.starts_at:
            raise DomainError("language support demand window must be positive")
        demand_ids.add(appointment_id)
        normalized_demands.append((demand, appointment_id, language))
    capacities: dict[str, int] = {}
    normalized_shifts: list[tuple[LanguageSupportShift, str, frozenset[str]]] = []
    for shift in shifts:
        staff_id = clean_code(shift.staff_id, "language support staff id")
        if staff_id in capacities:
            raise DomainError(f"duplicate language support shift: {staff_id}")
        if shift.ends_at <= shift.starts_at or shift.maximum_appointments < 1:
            raise DomainError("language support shift window and capacity are invalid")
        languages = frozenset(clean_code(value, "supported language").lower() for value in shift.languages)
        if not languages:
            raise DomainError("language support shift must include a language")
        capacities[staff_id] = shift.maximum_appointments
        normalized_shifts.append((shift, staff_id, languages))
    assignments: list[LanguageSupportAssignment] = []
    for demand, appointment_id, language in sorted(normalized_demands, key=lambda item: (item[0].starts_at, item[1])):
        eligible = [
            (shift, staff_id)
            for shift, staff_id, languages in normalized_shifts
            if language in languages
            and shift.starts_at <= demand.starts_at
            and shift.ends_at >= demand.ends_at
            and capacities[staff_id] > 0
        ]
        if not eligible:
            reason = (
                "no_qualified_shift"
                if not any(language in languages for _, _, languages in normalized_shifts)
                else "capacity_unavailable"
            )
            assignments.append(LanguageSupportAssignment(appointment_id, None, reason))
            continue
        _, staff_id = min(eligible, key=lambda item: (-capacities[item[1]], item[1]))
        capacities[staff_id] -= 1
        assignments.append(LanguageSupportAssignment(appointment_id, staff_id, None))
    return assignments
