"""Qualification-aware break coverage for clinic operations staff."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import DomainError, clean_code, clean_codes, parse_time


@dataclass(frozen=True, slots=True)
class BreakRequest:
    break_id: str
    staff_id: str
    earliest_start: str
    latest_end: str
    duration_minutes: int
    required_qualifications: set[str]
    priority: int


@dataclass(frozen=True, slots=True)
class ReliefStaff:
    staff_id: str
    qualifications: set[str]
    available_from: str
    available_until: str
    maximum_breaks: int


@dataclass(frozen=True, slots=True)
class BreakAssignment:
    break_id: str
    relief_staff_id: str | None
    starts_at: str | None
    ends_at: str | None
    assigned: bool
    reason: str


def schedule_break_coverage(requests: list[BreakRequest], relief_staff: list[ReliefStaff]) -> list[BreakAssignment]:
    """Place break coverage inside allowed windows without relief overlap."""
    staff_by_id: dict[str, tuple[ReliefStaff, datetime, datetime]] = {}
    for staff in relief_staff:
        staff_id = clean_code(staff.staff_id, "relief staff id")
        if staff_id in staff_by_id:
            raise DomainError(f"duplicate relief staff id: {staff_id}")
        available_from = parse_time(staff.available_from, "available_from")
        available_until = parse_time(staff.available_until, "available_until")
        if available_until <= available_from:
            raise DomainError("relief availability must have positive duration")
        if (
            isinstance(staff.maximum_breaks, bool)
            or not isinstance(staff.maximum_breaks, int)
            or not 1 <= staff.maximum_breaks <= 20
        ):
            raise DomainError("maximum_breaks must be from 1 through 20")
        staff_by_id[staff_id] = (
            ReliefStaff(
                staff_id,
                clean_codes(staff.qualifications, "relief qualification"),
                staff.available_from,
                staff.available_until,
                staff.maximum_breaks,
            ),
            available_from,
            available_until,
        )

    seen: set[str] = set()
    normalized: list[tuple[BreakRequest, datetime, datetime]] = []
    for request in requests:
        break_id = clean_code(request.break_id, "break id")
        if break_id in seen:
            raise DomainError(f"duplicate break request id: {break_id}")
        seen.add(break_id)
        earliest = parse_time(request.earliest_start, "earliest_start")
        latest = parse_time(request.latest_end, "latest_end")
        if latest <= earliest:
            raise DomainError("break latest_end must follow earliest_start")
        if (
            isinstance(request.duration_minutes, bool)
            or not isinstance(request.duration_minutes, int)
            or not 5 <= request.duration_minutes <= 120
        ):
            raise DomainError("break duration_minutes must be from 5 through 120")
        if earliest + timedelta(minutes=request.duration_minutes) > latest:
            raise DomainError("break duration does not fit its allowed window")
        if (
            isinstance(request.priority, bool)
            or not isinstance(request.priority, int)
            or not 1 <= request.priority <= 5
        ):
            raise DomainError("break priority must be from 1 through 5")
        normalized.append(
            (
                BreakRequest(
                    break_id,
                    clean_code(request.staff_id, "staff id"),
                    request.earliest_start,
                    request.latest_end,
                    request.duration_minutes,
                    clean_codes(request.required_qualifications, "required qualification"),
                    request.priority,
                ),
                earliest,
                latest,
            )
        )

    schedules: dict[str, list[tuple[datetime, datetime]]] = {staff_id: [] for staff_id in staff_by_id}
    assignments: list[BreakAssignment] = []
    for request, earliest, latest in sorted(
        normalized,
        key=lambda item: (-item[0].priority, item[2], item[0].break_id),
    ):
        options: list[tuple[datetime, int, str]] = []
        duration = timedelta(minutes=request.duration_minutes)
        for staff_id, (staff, available_from, available_until) in staff_by_id.items():
            windows = sorted(schedules[staff_id])
            if staff_id == request.staff_id:
                continue
            if len(windows) >= staff.maximum_breaks:
                continue
            if not request.required_qualifications <= staff.qualifications:
                continue
            start = max(earliest, available_from)
            for occupied_start, occupied_end in windows:
                if start + duration <= occupied_start:
                    break
                if start < occupied_end:
                    start = occupied_end
            if start + duration <= min(latest, available_until):
                options.append((start, len(windows), staff_id))

        if not options:
            assignments.append(BreakAssignment(request.break_id, None, None, None, False, "no qualified relief window"))
            continue
        start, _, selected = min(options, key=lambda option: (option[0], option[1], option[2]))
        end = start + duration
        schedules[selected].append((start, end))
        assignments.append(
            BreakAssignment(
                request.break_id,
                selected,
                start.isoformat(),
                end.isoformat(),
                True,
                "break coverage scheduled",
            )
        )
    return assignments
