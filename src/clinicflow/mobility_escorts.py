"""Allocate trained mobility escorts to appointment arrival windows."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class MobilityEscortShift:
    escort_id: str
    clinic_id: str
    start_minute: int
    end_minute: int
    accessible_transfer_trained: bool
    maximum_concurrent: int = 1


@dataclass(frozen=True, slots=True)
class MobilityEscortRequest:
    appointment_id: str
    clinic_id: str
    start_minute: int
    end_minute: int
    accessible_transfer_required: bool = False


@dataclass(frozen=True, slots=True)
class MobilityEscortAllocation:
    appointment_id: str
    escort_id: str | None
    assigned: bool


def allocate_mobility_escorts(
    requests: list[MobilityEscortRequest],
    shifts: list[MobilityEscortShift],
) -> list[MobilityEscortAllocation]:
    """Assign escorts while respecting coverage, training, and concurrent capacity."""
    normalized_shifts: list[MobilityEscortShift] = []
    shift_ids: set[str] = set()
    for shift in shifts:
        escort_id = clean_code(shift.escort_id, "mobility escort id")
        clinic_id = clean_code(shift.clinic_id, "mobility escort clinic id")
        if escort_id in shift_ids:
            raise DomainError(f"duplicate mobility escort shift: {escort_id}")
        if shift.start_minute < 0 or shift.end_minute <= shift.start_minute or shift.maximum_concurrent < 1:
            raise DomainError("mobility escort shift has invalid timing or capacity")
        shift_ids.add(escort_id)
        normalized_shifts.append(
            MobilityEscortShift(
                escort_id,
                clinic_id,
                shift.start_minute,
                shift.end_minute,
                shift.accessible_transfer_trained,
                shift.maximum_concurrent,
            )
        )

    request_ids: set[str] = set()
    normalized_requests: list[MobilityEscortRequest] = []
    for request in requests:
        appointment_id = clean_code(request.appointment_id, "escort appointment id")
        clinic_id = clean_code(request.clinic_id, "escort clinic id")
        if appointment_id in request_ids:
            raise DomainError(f"duplicate mobility escort request: {appointment_id}")
        if request.start_minute < 0 or request.end_minute <= request.start_minute:
            raise DomainError("mobility escort request has invalid timing")
        request_ids.add(appointment_id)
        normalized_requests.append(
            MobilityEscortRequest(
                appointment_id,
                clinic_id,
                request.start_minute,
                request.end_minute,
                request.accessible_transfer_required,
            )
        )

    bookings: dict[str, list[tuple[int, int]]] = {shift.escort_id: [] for shift in normalized_shifts}
    allocations: list[MobilityEscortAllocation] = []
    for request in sorted(
        normalized_requests,
        key=lambda item: (
            item.start_minute,
            not item.accessible_transfer_required,
            item.appointment_id,
        ),
    ):
        candidates: list[tuple[int, str, MobilityEscortShift]] = []
        for shift in normalized_shifts:
            if (
                shift.clinic_id != request.clinic_id
                or shift.start_minute > request.start_minute
                or shift.end_minute < request.end_minute
                or (request.accessible_transfer_required and not shift.accessible_transfer_trained)
            ):
                continue
            overlap = sum(
                1
                for start, end in bookings[shift.escort_id]
                if start < request.end_minute and request.start_minute < end
            )
            if overlap < shift.maximum_concurrent:
                candidates.append((overlap, shift.escort_id, shift))
        if not candidates:
            allocations.append(MobilityEscortAllocation(request.appointment_id, None, False))
            continue
        _, escort_id, _ = min(candidates)
        bookings[escort_id].append((request.start_minute, request.end_minute))
        allocations.append(MobilityEscortAllocation(request.appointment_id, escort_id, True))
    return allocations
