"""Assess non-clinical room access logs against authorization windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from clinicflow.models import DomainError


@dataclass(frozen=True, slots=True)
class RoomAccessRequirement:
    room_id: str
    staff_id: str
    valid_from: datetime
    valid_to: datetime
    escort_required: bool = False


@dataclass(frozen=True, slots=True)
class RoomAccessEvent:
    event_id: str
    room_id: str
    staff_id: str
    occurred_at: datetime
    escort_present: bool


@dataclass(frozen=True, slots=True)
class RoomAccessFinding:
    event_id: str
    room_id: str
    staff_id: str
    blockers: tuple[str, ...]
    authorized: bool


def assess_room_access_logs(
    requirements: list[RoomAccessRequirement], events: list[RoomAccessEvent]
) -> list[RoomAccessFinding]:
    """Detect access outside grants and missing escorts."""
    configured: dict[tuple[str, str], RoomAccessRequirement] = {}
    for requirement in requirements:
        room = _text(requirement.room_id, "access room", maximum=120)
        staff = _text(requirement.staff_id, "access staff", maximum=120)
        start, end = (
            _checked_time(requirement.valid_from, "access grant start"),
            _checked_time(requirement.valid_to, "access grant end"),
        )
        key = (room.casefold(), staff.casefold())
        if key in configured or end <= start:
            raise DomainError(f"invalid or duplicate room access requirement {room}/{staff}")
        configured[key] = RoomAccessRequirement(room, staff, start, end, requirement.escort_required)
    seen: set[str] = set()
    findings: list[RoomAccessFinding] = []
    for event in events:
        event_id = _text(event.event_id, "room access event", maximum=120)
        room = _text(event.room_id, "room access event room", maximum=120)
        staff = _text(event.staff_id, "room access event staff", maximum=120)
        occurred = _checked_time(event.occurred_at, "room access event time")
        if event_id.casefold() in seen:
            raise DomainError(f"duplicate room access event {event_id}")
        seen.add(event_id.casefold())
        grant = configured.get((room.casefold(), staff.casefold()))
        blockers: list[str] = []
        if grant is None:
            blockers.append("grant_missing")
        else:
            if occurred < grant.valid_from or occurred >= grant.valid_to:
                blockers.append("outside_access_window")
            if grant.escort_required and not event.escort_present:
                blockers.append("escort_missing")
        findings.append(RoomAccessFinding(event_id, room, staff, tuple(blockers), not blockers))
    return sorted(findings, key=lambda row: (row.authorized, -len(row.blockers), row.event_id))


def _text(value: str, field: str, *, maximum: int) -> str:
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > maximum:
        raise DomainError(f"{field} is invalid")
    return normalized


def _checked_time(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DomainError(f"{field} must include a timezone")
    return value
