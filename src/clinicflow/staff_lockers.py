"""Allocate secure lockers to clinic shifts with custody controls."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class StaffLocker:
    locker_id: str
    clinic_id: str
    accessible: bool
    key_verified: bool


@dataclass(frozen=True, slots=True)
class StaffLockerRequest:
    staff_id: str
    clinic_id: str
    shift_start: int
    shift_end: int
    accessible_required: bool
    priority: int


@dataclass(frozen=True, slots=True)
class StaffLockerAssignment:
    staff_id: str
    locker_id: str | None
    assigned: bool


def allocate_staff_lockers(
    lockers: list[StaffLocker], requests: list[StaffLockerRequest]
) -> list[StaffLockerAssignment]:
    """Assign key-verified lockers without overlapping staff shifts."""
    available: dict[str, StaffLocker] = {}
    for locker in lockers:
        locker_id = clean_code(locker.locker_id, "staff locker id")
        clinic_id = clean_code(locker.clinic_id, "staff locker clinic id")
        if locker_id in available:
            raise DomainError(f"duplicate staff locker: {locker_id}")
        if locker.key_verified:
            available[locker_id] = StaffLocker(locker_id, clinic_id, locker.accessible, True)
    normalized: list[StaffLockerRequest] = []
    staff_ids: set[str] = set()
    for request in requests:
        staff_id = clean_code(request.staff_id, "locker staff id")
        clinic_id = clean_code(request.clinic_id, "locker request clinic id")
        if staff_id in staff_ids:
            raise DomainError(f"duplicate staff locker request: {staff_id}")
        if request.shift_start < 0 or request.shift_end <= request.shift_start or request.priority < 0:
            raise DomainError("staff locker request timing is invalid")
        staff_ids.add(staff_id)
        normalized.append(
            StaffLockerRequest(
                staff_id,
                clinic_id,
                request.shift_start,
                request.shift_end,
                request.accessible_required,
                request.priority,
            )
        )
    reservations: dict[str, list[tuple[int, int]]] = {locker_id: [] for locker_id in available}
    result: list[StaffLockerAssignment] = []
    for request in sorted(normalized, key=lambda item: (-item.priority, item.shift_start, item.staff_id)):
        selected = next(
            (
                locker_id
                for locker_id, locker in sorted(available.items())
                if locker.clinic_id == request.clinic_id
                and (not request.accessible_required or locker.accessible)
                and all(
                    request.shift_end <= start or request.shift_start >= end for start, end in reservations[locker_id]
                )
            ),
            None,
        )
        if selected is not None:
            reservations[selected].append((request.shift_start, request.shift_end))
        result.append(StaffLockerAssignment(request.staff_id, selected, selected is not None))
    return result
