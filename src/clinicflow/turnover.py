"""Room turnover planning between consecutive clinic appointments."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import DomainError, clean_code, clean_text, parse_time


@dataclass(frozen=True, slots=True)
class RoomUse:
    appointment_id: str
    room_id: str
    procedure: str
    starts_at: str
    ends_at: str


@dataclass(frozen=True, slots=True)
class TurnoverTask:
    room_id: str
    after_appointment_id: str
    before_appointment_id: str
    required_minutes: int
    available_minutes: int
    shortfall_minutes: int


def plan_room_turnover(uses: list[RoomUse], procedure_minutes: dict[str, int]) -> list[TurnoverTask]:
    """Calculate room reset capacity and conflicts for each consecutive use."""
    normalized_rules: dict[str, int] = {}
    for procedure, minutes in procedure_minutes.items():
        name = clean_text(procedure, "procedure", 160).lower()
        if isinstance(minutes, bool) or not isinstance(minutes, int) or not 0 <= minutes <= 240:
            raise DomainError("turnover minutes must be from 0 through 240")
        normalized_rules[name] = minutes
    seen: set[str] = set()
    by_room: dict[str, list[tuple[RoomUse, datetime, datetime]]] = {}
    for use in uses:
        appointment_id = clean_code(use.appointment_id, "appointment id")
        if appointment_id in seen:
            raise DomainError(f"duplicate appointment id: {appointment_id}")
        seen.add(appointment_id)
        room_id = clean_code(use.room_id, "room id")
        procedure = clean_text(use.procedure, "procedure", 160).lower()
        starts = parse_time(use.starts_at, "starts_at")
        ends = parse_time(use.ends_at, "ends_at")
        if ends <= starts:
            raise DomainError("room use ends_at must follow starts_at")
        by_room.setdefault(room_id, []).append(
            (RoomUse(appointment_id, room_id, procedure, use.starts_at, use.ends_at), starts, ends)
        )

    tasks: list[TurnoverTask] = []
    for room_id, room_uses in by_room.items():
        room_uses.sort(key=lambda item: (item[1], item[0].appointment_id))
        for previous, following in zip(room_uses, room_uses[1:], strict=False):
            previous_use, _, previous_end = previous
            following_use, following_start, _ = following
            required = normalized_rules.get(previous_use.procedure, 15)
            available = int((following_start - previous_end) / timedelta(minutes=1))
            tasks.append(
                TurnoverTask(
                    room_id,
                    previous_use.appointment_id,
                    following_use.appointment_id,
                    required,
                    max(0, available),
                    max(0, required - available),
                )
            )
    return sorted(tasks, key=lambda task: (task.room_id, task.after_appointment_id))
