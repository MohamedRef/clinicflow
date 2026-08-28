"""Appointment room preparation readiness and setup deadlines."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class RoomReadiness:
    room_id: str
    cleaned_at: str
    available_assets: tuple[str, ...]
    blocked_until: str | None = None


@dataclass(frozen=True, slots=True)
class PreparationRequest:
    appointment_id: str
    room_id: str
    starts_at: str
    required_assets: tuple[str, ...]
    setup_minutes: int


@dataclass(frozen=True, slots=True)
class PreparationAssessment:
    appointment_id: str
    room_id: str
    setup_must_start_at: str
    missing_assets: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    ready: bool


def assess_room_preparation(
    requests: list[PreparationRequest],
    rooms: list[RoomReadiness],
    assessed_at: str,
) -> list[PreparationAssessment]:
    """Assess whether rooms can be prepared before appointment start."""
    assessment_time = parse_time(assessed_at, "assessed_at")
    indexed_rooms = _room_index(rooms, assessment_time)
    seen: set[str] = set()
    assessments: list[PreparationAssessment] = []
    for request in requests:
        appointment_id = clean_code(request.appointment_id, "preparation appointment id")
        key = appointment_id.casefold()
        if key in seen:
            raise DomainError(f"duplicate preparation appointment id: {appointment_id}")
        seen.add(key)
        room_id = clean_code(request.room_id, "preparation room id")
        starts_at = parse_time(request.starts_at, "starts_at")
        setup_minutes = _setup_minutes(request.setup_minutes)
        required = _asset_set(request.required_assets, "required asset")
        readiness = indexed_rooms.get(room_id.casefold())
        if readiness is None:
            raise DomainError(f"unknown preparation room: {room_id}")
        room, cleaned_at, blocked_until, available = readiness
        setup_start = starts_at - timedelta(minutes=setup_minutes)
        reasons: list[str] = []
        if assessment_time > setup_start:
            reasons.append("setup_window_missed")
        if cleaned_at > setup_start:
            reasons.append("cleaning_incomplete_before_setup")
        if blocked_until is not None and blocked_until > setup_start:
            reasons.append("room_block_overlaps_setup")
        missing = tuple(sorted(required - available))
        if missing:
            reasons.append("assets_missing")
        assessments.append(
            PreparationAssessment(
                appointment_id,
                room.room_id,
                setup_start.isoformat(),
                missing,
                tuple(reasons),
                not reasons,
            )
        )
    return sorted(
        assessments,
        key=lambda item: (item.ready, item.setup_must_start_at, item.appointment_id),
    )


def _room_index(
    rooms: list[RoomReadiness], assessed_at: datetime
) -> dict[str, tuple[RoomReadiness, datetime, datetime | None, set[str]]]:
    indexed: dict[str, tuple[RoomReadiness, datetime, datetime | None, set[str]]] = {}
    for room in rooms:
        room_id = clean_code(room.room_id, "readiness room id")
        key = room_id.casefold()
        if key in indexed:
            raise DomainError(f"duplicate room readiness: {room_id}")
        cleaned_at = parse_time(room.cleaned_at, "cleaned_at")
        if cleaned_at > assessed_at + timedelta(days=7):
            raise DomainError("cleaning readiness cannot be more than seven days in the future")
        blocked_until = parse_time(room.blocked_until, "blocked_until") if room.blocked_until else None
        available = _asset_set(room.available_assets, "available asset")
        indexed[key] = (
            RoomReadiness(room_id, room.cleaned_at, tuple(sorted(available)), room.blocked_until),
            cleaned_at,
            blocked_until,
            available,
        )
    return indexed


def _asset_set(values: tuple[str, ...], field: str) -> set[str]:
    assets: set[str] = set()
    for value in values:
        asset = clean_code(value, field).casefold()
        if asset in assets:
            raise DomainError(f"duplicate {field}: {value}")
        assets.add(asset)
    return assets


def _setup_minutes(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 8 * 60:
        raise DomainError("setup minutes must be from 0 through 480")
    return value
