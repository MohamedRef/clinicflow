"""Schedule waiting-room sanitation rotations around occupancy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import DomainError


@dataclass(frozen=True, slots=True)
class WaitingRoomSanitationNeed:
    zone_id: str
    last_cleaned_at: datetime
    maximum_interval_minutes: int
    current_occupancy: int


@dataclass(frozen=True, slots=True)
class SanitationTeamWindow:
    team_id: str
    starts_at: datetime
    capacity: int


@dataclass(frozen=True, slots=True)
class WaitingRoomSanitationAssignment:
    zone_id: str
    team_id: str | None
    overdue_minutes: int
    assigned: bool


def _aware(value: object, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise DomainError(f"{field} must be timezone-aware")
    return value


def _whole(value: object, field: str, minimum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise DomainError(f"{field} must be an integer of at least {minimum}")
    return value


def schedule_waiting_room_sanitation(
    needs: list[WaitingRoomSanitationNeed], windows: list[SanitationTeamWindow], *, as_of: datetime
) -> list[WaitingRoomSanitationAssignment]:
    """Assign the most overdue and most occupied zones to available teams."""
    now = _aware(as_of, "sanitation assessment time")
    seen_teams: set[str] = set()
    remaining: list[int] = []
    for window in windows:
        if not isinstance(window.team_id, str) or not window.team_id.strip():
            raise DomainError("sanitation team id is required")
        if window.team_id.casefold() in seen_teams:
            raise DomainError(f"duplicate sanitation team {window.team_id}")
        seen_teams.add(window.team_id.casefold())
        _aware(window.starts_at, "sanitation team start")
        remaining.append(_whole(window.capacity, "sanitation team capacity", 1))
    seen_zones: set[str] = set()
    ranked: list[tuple[WaitingRoomSanitationNeed, str, int]] = []
    for need in needs:
        if not isinstance(need.zone_id, str) or not need.zone_id.strip():
            raise DomainError("waiting room zone id is required")
        zone_id = " ".join(need.zone_id.split())
        if zone_id.casefold() in seen_zones:
            raise DomainError(f"duplicate waiting room sanitation need {zone_id}")
        seen_zones.add(zone_id.casefold())
        cleaned = _aware(need.last_cleaned_at, "waiting room last cleaned time")
        interval = _whole(need.maximum_interval_minutes, "maximum sanitation interval", 1)
        _whole(need.current_occupancy, "waiting room occupancy", 0)
        if cleaned > now:
            raise DomainError("waiting room cleaning cannot be in the future")
        due_at = cleaned + timedelta(minutes=interval)
        overdue = max(0, int((now - due_at).total_seconds() // 60))
        ranked.append((need, zone_id, overdue))
    ranked.sort(key=lambda item: (-item[2], -item[0].current_occupancy, item[1]))
    assignments: list[WaitingRoomSanitationAssignment] = []
    for _, zone_id, overdue in ranked:
        choices = [index for index, window in enumerate(windows) if remaining[index] and window.starts_at <= now]
        if not choices:
            assignments.append(WaitingRoomSanitationAssignment(zone_id, None, overdue, False))
            continue
        selected = max(choices, key=lambda index: (remaining[index], windows[index].team_id))
        remaining[selected] -= 1
        assignments.append(WaitingRoomSanitationAssignment(zone_id, windows[selected].team_id, overdue, True))
    return assignments
