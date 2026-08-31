"""Forecast reception-desk pressure from appointment arrivals."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class ReceptionArrival:
    appointment_id: str
    clinic_id: str
    expected_at: str
    service_minutes: int


@dataclass(frozen=True, slots=True)
class ReceptionDeskCapacity:
    clinic_id: str
    concurrent_desks: int


@dataclass(frozen=True, slots=True)
class ReceptionCapacityFinding:
    clinic_id: str
    peak_arrivals: int
    concurrent_desks: int
    shortfall: int


def assess_reception_capacity(
    arrivals: list[ReceptionArrival], capacities: list[ReceptionDeskCapacity]
) -> list[ReceptionCapacityFinding]:
    """Find clinics whose overlapping arrival workload exceeds staffed desks."""
    configured: dict[str, int] = {}
    for capacity_row in capacities:
        clinic_id = clean_code(capacity_row.clinic_id, "reception capacity clinic")
        if clinic_id in configured:
            raise DomainError(f"duplicate reception capacity: {clinic_id}")
        if (
            not isinstance(capacity_row.concurrent_desks, int)
            or isinstance(capacity_row.concurrent_desks, bool)
            or capacity_row.concurrent_desks < 0
        ):
            raise DomainError("reception desk capacity must be a non-negative integer")
        configured[clinic_id] = capacity_row.concurrent_desks
    seen: set[str] = set()
    events: dict[str, list[tuple[datetime, int]]] = {}
    for arrival in arrivals:
        appointment_id = clean_code(arrival.appointment_id, "reception appointment id")
        clinic_id = clean_code(arrival.clinic_id, "reception arrival clinic")
        if appointment_id in seen:
            raise DomainError(f"duplicate reception arrival: {appointment_id}")
        if clinic_id not in configured:
            raise DomainError(f"reception capacity missing for clinic: {clinic_id}")
        if (
            not isinstance(arrival.service_minutes, int)
            or isinstance(arrival.service_minutes, bool)
            or arrival.service_minutes < 1
        ):
            raise DomainError("reception service time must be a positive whole minute")
        seen.add(appointment_id)
        start = parse_time(arrival.expected_at, "reception expected_at")
        end = start + timedelta(minutes=arrival.service_minutes)
        events.setdefault(clinic_id, []).extend(((start, 1), (end, -1)))
    findings: list[ReceptionCapacityFinding] = []
    for clinic_id, points in events.items():
        points.sort(key=lambda point: (point[0], point[1]))
        active = 0
        peak = 0
        for _, delta in points:
            active += delta
            peak = max(peak, active)
        desk_count = configured[clinic_id]
        if peak > desk_count:
            findings.append(ReceptionCapacityFinding(clinic_id, peak, desk_count, peak - desk_count))
    return sorted(findings, key=lambda item: (-item.shortfall, item.clinic_id))
