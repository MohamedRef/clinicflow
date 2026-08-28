"""Controlled appointment overbooking based on historical attendance risk."""

from dataclasses import dataclass

from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class OverbookingSlot:
    slot_id: str
    room_id: str
    starts_at: str
    ends_at: str
    standard_capacity: int
    maximum_capacity: int
    maximum_absence_probability: float


@dataclass(frozen=True, slots=True)
class OverbookingRequest:
    request_id: str
    slot_id: str
    absence_probability: float
    priority: int
    requested_at: str


@dataclass(frozen=True, slots=True)
class OverbookingDecision:
    request_id: str
    slot_id: str
    accepted: bool
    position: int | None
    reason: str


def plan_appointment_overbooking(
    slots: list[OverbookingSlot], requests: list[OverbookingRequest], existing_bookings: dict[str, int]
) -> list[OverbookingDecision]:
    """Accept bounded extra appointments without exceeding room safety limits."""
    normalized_slots: dict[str, OverbookingSlot] = {}
    for slot in slots:
        slot_id = clean_code(slot.slot_id, "overbooking slot id")
        room_id = clean_code(slot.room_id, "overbooking room id")
        if slot_id in normalized_slots:
            raise DomainError(f"duplicate overbooking slot id: {slot_id}")
        starts_at = parse_time(slot.starts_at, "starts_at")
        if parse_time(slot.ends_at, "ends_at") <= starts_at:
            raise DomainError("overbooking slot must have positive duration")
        if (
            isinstance(slot.standard_capacity, bool)
            or not isinstance(slot.standard_capacity, int)
            or slot.standard_capacity < 1
            or isinstance(slot.maximum_capacity, bool)
            or not isinstance(slot.maximum_capacity, int)
            or slot.maximum_capacity < slot.standard_capacity
        ):
            raise DomainError("overbooking capacities are invalid")
        if not 0 <= slot.maximum_absence_probability <= 1:
            raise DomainError("maximum absence probability must be between zero and one")
        normalized_slots[slot_id] = OverbookingSlot(
            slot_id,
            room_id,
            slot.starts_at,
            slot.ends_at,
            slot.standard_capacity,
            slot.maximum_capacity,
            slot.maximum_absence_probability,
        )
    occupancy: dict[str, int] = {}
    for slot_id, count in existing_bookings.items():
        normalized_id = clean_code(slot_id, "existing booking slot id")
        if normalized_id not in normalized_slots:
            raise DomainError(f"unknown existing booking slot: {normalized_id}")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise DomainError("existing booking count must be a non-negative integer")
        if count > normalized_slots[normalized_id].maximum_capacity:
            raise DomainError("existing bookings exceed maximum capacity")
        occupancy[normalized_id] = count
    seen: set[str] = set()
    normalized_requests: list[OverbookingRequest] = []
    for request in requests:
        request_id = clean_code(request.request_id, "overbooking request id")
        slot_id = clean_code(request.slot_id, "overbooking request slot id")
        if request_id in seen:
            raise DomainError(f"duplicate overbooking request id: {request_id}")
        seen.add(request_id)
        if slot_id not in normalized_slots:
            raise DomainError(f"unknown overbooking slot: {slot_id}")
        if not 0 <= request.absence_probability <= 1:
            raise DomainError("absence probability must be between zero and one")
        if (
            isinstance(request.priority, bool)
            or not isinstance(request.priority, int)
            or not 1 <= request.priority <= 5
        ):
            raise DomainError("overbooking priority must be from 1 through 5")
        parse_time(request.requested_at, "requested_at")
        normalized_requests.append(
            OverbookingRequest(request_id, slot_id, request.absence_probability, request.priority, request.requested_at)
        )
    decisions: list[OverbookingDecision] = []
    for request in sorted(
        normalized_requests, key=lambda row: (-row.priority, -row.absence_probability, row.requested_at, row.request_id)
    ):
        slot = normalized_slots[request.slot_id]
        count = occupancy.get(request.slot_id, 0)
        if count < slot.standard_capacity:
            reason = "standard capacity available"
        elif request.absence_probability < slot.maximum_absence_probability:
            decisions.append(
                OverbookingDecision(request.request_id, request.slot_id, False, None, "attendance risk too high")
            )
            continue
        elif count >= slot.maximum_capacity:
            decisions.append(
                OverbookingDecision(request.request_id, request.slot_id, False, None, "maximum capacity reached")
            )
            continue
        else:
            reason = "controlled overbooking approved"
        count += 1
        occupancy[request.slot_id] = count
        decisions.append(OverbookingDecision(request.request_id, request.slot_id, True, count, reason))
    return decisions
