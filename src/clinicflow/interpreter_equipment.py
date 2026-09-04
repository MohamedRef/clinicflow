"""Allocate non-clinical interpreter equipment to appointment support needs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import DomainError


@dataclass(frozen=True, slots=True)
class InterpreterEquipmentDemand:
    appointment_id: str
    language: str
    starts_at: datetime
    needs_video: bool = False


@dataclass(frozen=True, slots=True)
class InterpreterEquipmentUnit:
    unit_id: str
    languages: tuple[str, ...]
    video_capable: bool
    available_at: datetime


@dataclass(frozen=True, slots=True)
class InterpreterEquipmentAssignment:
    appointment_id: str
    unit_id: str | None
    assigned: bool
    reason: str


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainError(f"{field} is required")
    return " ".join(value.split())


def _time(value: object, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise DomainError(f"{field} must be timezone-aware")
    return value


def allocate_interpreter_equipment(
    demands: list[InterpreterEquipmentDemand], units: list[InterpreterEquipmentUnit]
) -> list[InterpreterEquipmentAssignment]:
    """Reserve compatible units for the earliest supported appointments."""
    capabilities: list[set[str]] = []
    seen_units: set[str] = set()
    for unit in units:
        unit_id = _text(unit.unit_id, "interpreter equipment unit id")
        identity = unit_id.casefold()
        if identity in seen_units:
            raise DomainError(f"duplicate interpreter equipment unit {unit_id}")
        seen_units.add(identity)
        languages = {_text(language, "interpreter equipment language").casefold() for language in unit.languages}
        if not languages:
            raise DomainError("interpreter equipment languages are required")
        _time(unit.available_at, "interpreter equipment availability")
        capabilities.append(languages)
    seen_appointments: set[str] = set()
    normalized: list[tuple[InterpreterEquipmentDemand, str, str, datetime]] = []
    for demand in demands:
        appointment_id = _text(demand.appointment_id, "interpreter equipment appointment id")
        language = _text(demand.language, "interpreter equipment demand language").casefold()
        starts_at = _time(demand.starts_at, "interpreter equipment appointment start")
        if appointment_id.casefold() in seen_appointments:
            raise DomainError(f"duplicate interpreter equipment appointment {appointment_id}")
        seen_appointments.add(appointment_id.casefold())
        normalized.append((demand, appointment_id, language, starts_at))
    normalized.sort(key=lambda item: (item[3], not item[0].needs_video, item[1]))
    used: set[int] = set()
    assignments: list[InterpreterEquipmentAssignment] = []
    for demand, appointment_id, language, starts_at in normalized:
        choices = [
            index
            for index, unit in enumerate(units)
            if index not in used
            and language in capabilities[index]
            and (unit.video_capable or not demand.needs_video)
            and unit.available_at <= starts_at
        ]
        if not choices:
            assignments.append(
                InterpreterEquipmentAssignment(appointment_id, None, False, "no compatible unit available")
            )
            continue
        selected = max(choices, key=lambda index: (units[index].available_at, units[index].unit_id))
        used.add(selected)
        assignments.append(
            InterpreterEquipmentAssignment(appointment_id, units[selected].unit_id, True, "compatible unit reserved")
        )
    return assignments
