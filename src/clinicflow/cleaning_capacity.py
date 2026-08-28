"""Risk-aware allocation of room cleaning teams between clinic uses."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import DomainError, clean_code, clean_codes, parse_time


@dataclass(frozen=True, slots=True)
class RoomCleaningDemand:
    task_id: str
    room_id: str
    ready_at: str
    due_at: str
    required_minutes: int
    required_certifications: set[str]
    risk: int


@dataclass(frozen=True, slots=True)
class CleaningTeam:
    team_id: str
    certifications: set[str]
    available_from: str
    available_until: str
    maximum_tasks: int


@dataclass(frozen=True, slots=True)
class CleaningAssignment:
    task_id: str
    team_id: str | None
    starts_at: str | None
    ends_at: str | None
    assigned: bool
    reason: str


def allocate_cleaning_capacity(
    demands: list[RoomCleaningDemand], teams: list[CleaningTeam]
) -> list[CleaningAssignment]:
    """Assign cleaning work before room deadlines without team overlap."""
    normalized_teams: dict[str, tuple[CleaningTeam, datetime, datetime]] = {}
    for team in teams:
        team_id = clean_code(team.team_id, "cleaning team id")
        if team_id in normalized_teams:
            raise DomainError(f"duplicate cleaning team id: {team_id}")
        available_from = parse_time(team.available_from, "available_from")
        available_until = parse_time(team.available_until, "available_until")
        if available_until <= available_from:
            raise DomainError("cleaning team availability must have positive duration")
        if (
            isinstance(team.maximum_tasks, bool)
            or not isinstance(team.maximum_tasks, int)
            or not 1 <= team.maximum_tasks <= 30
        ):
            raise DomainError("cleaning maximum_tasks must be from 1 through 30")
        normalized_teams[team_id] = (
            CleaningTeam(
                team_id,
                clean_codes(team.certifications, "cleaning certification"),
                team.available_from,
                team.available_until,
                team.maximum_tasks,
            ),
            available_from,
            available_until,
        )

    seen: set[str] = set()
    normalized_demands: list[tuple[RoomCleaningDemand, datetime, datetime]] = []
    for demand in demands:
        task_id = clean_code(demand.task_id, "cleaning task id")
        if task_id in seen:
            raise DomainError(f"duplicate cleaning task id: {task_id}")
        seen.add(task_id)
        ready_at = parse_time(demand.ready_at, "ready_at")
        due_at = parse_time(demand.due_at, "due_at")
        if due_at <= ready_at:
            raise DomainError("cleaning due_at must follow ready_at")
        if (
            isinstance(demand.required_minutes, bool)
            or not isinstance(demand.required_minutes, int)
            or not 1 <= demand.required_minutes <= 240
        ):
            raise DomainError("cleaning required_minutes must be from 1 through 240")
        if isinstance(demand.risk, bool) or not isinstance(demand.risk, int) or not 1 <= demand.risk <= 5:
            raise DomainError("cleaning risk must be from 1 through 5")
        normalized_demands.append(
            (
                RoomCleaningDemand(
                    task_id,
                    clean_code(demand.room_id, "cleaning room id"),
                    demand.ready_at,
                    demand.due_at,
                    demand.required_minutes,
                    clean_codes(demand.required_certifications, "required cleaning certification"),
                    demand.risk,
                ),
                ready_at,
                due_at,
            )
        )

    schedules: dict[str, list[tuple[datetime, datetime]]] = {team_id: [] for team_id in normalized_teams}
    assignments: list[CleaningAssignment] = []
    for demand, ready_at, due_at in sorted(
        normalized_demands, key=lambda item: (-item[0].risk, item[2], item[0].task_id)
    ):
        candidates: list[tuple[datetime, int, str]] = []
        for team_id, (team, available_from, available_until) in normalized_teams.items():
            windows = sorted(schedules[team_id])
            if len(windows) >= team.maximum_tasks or not demand.required_certifications <= team.certifications:
                continue
            start = max(ready_at, available_from)
            for occupied_start, occupied_end in windows:
                if start + timedelta(minutes=demand.required_minutes) <= occupied_start:
                    break
                if start < occupied_end:
                    start = occupied_end
            end = start + timedelta(minutes=demand.required_minutes)
            if end <= min(due_at, available_until):
                candidates.append((start, len(windows), team_id))
        if not candidates:
            assignments.append(
                CleaningAssignment(demand.task_id, None, None, None, False, "no certified team before deadline")
            )
            continue
        start, _, team_id = min(candidates, key=lambda item: (item[0], item[1], item[2]))
        end = start + timedelta(minutes=demand.required_minutes)
        schedules[team_id].append((start, end))
        assignments.append(
            CleaningAssignment(
                demand.task_id, team_id, start.isoformat(), end.isoformat(), True, "cleaning team assigned"
            )
        )
    return assignments
