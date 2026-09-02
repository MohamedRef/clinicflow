"""Allocate portable privacy screens to room turnover demands."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class PrivacyScreen:
    screen_id: str
    clinic_id: str
    inspected_day: int
    damaged: bool


@dataclass(frozen=True, slots=True)
class PrivacyScreenDemand:
    room_id: str
    clinic_id: str
    start_minute: int
    end_minute: int
    priority: int


@dataclass(frozen=True, slots=True)
class PrivacyScreenAssignment:
    room_id: str
    screen_id: str | None
    assigned: bool
    reason: str


def allocate_privacy_screens(
    screens: list[PrivacyScreen],
    demands: list[PrivacyScreenDemand],
    current_day: int,
    maximum_inspection_age_days: int,
) -> list[PrivacyScreenAssignment]:
    """Assign inspected screens without overlapping room reservations."""
    if current_day < 0 or maximum_inspection_age_days < 0:
        raise DomainError("privacy screen timing is invalid")
    usable: dict[str, PrivacyScreen] = {}
    for screen in screens:
        screen_id = clean_code(screen.screen_id, "privacy screen id")
        clinic_id = clean_code(screen.clinic_id, "privacy screen clinic id")
        if screen_id in usable:
            raise DomainError(f"duplicate privacy screen: {screen_id}")
        if screen.inspected_day < 0 or screen.inspected_day > current_day:
            raise DomainError("privacy screen inspection day is invalid")
        if not screen.damaged and current_day - screen.inspected_day <= maximum_inspection_age_days:
            usable[screen_id] = PrivacyScreen(screen_id, clinic_id, screen.inspected_day, False)

    normalized: list[PrivacyScreenDemand] = []
    rooms: set[str] = set()
    for demand in demands:
        room_id = clean_code(demand.room_id, "privacy screen room id")
        clinic_id = clean_code(demand.clinic_id, "privacy screen demand clinic id")
        if room_id in rooms:
            raise DomainError(f"duplicate privacy screen demand: {room_id}")
        if demand.start_minute < 0 or demand.end_minute <= demand.start_minute or demand.priority < 0:
            raise DomainError("privacy screen demand timing is invalid")
        rooms.add(room_id)
        normalized.append(
            PrivacyScreenDemand(room_id, clinic_id, demand.start_minute, demand.end_minute, demand.priority)
        )

    reservations: dict[str, list[tuple[int, int]]] = {screen_id: [] for screen_id in usable}
    assignments: list[PrivacyScreenAssignment] = []
    for demand in sorted(normalized, key=lambda item: (-item.priority, item.start_minute, item.room_id)):
        selected = next(
            (
                screen_id
                for screen_id, screen in sorted(usable.items())
                if screen.clinic_id == demand.clinic_id
                and all(
                    demand.end_minute <= start or demand.start_minute >= end for start, end in reservations[screen_id]
                )
            ),
            None,
        )
        if selected is None:
            assignments.append(PrivacyScreenAssignment(demand.room_id, None, False, "no_available_screen"))
        else:
            reservations[selected].append((demand.start_minute, demand.end_minute))
            assignments.append(PrivacyScreenAssignment(demand.room_id, selected, True, "assigned"))
    return assignments
