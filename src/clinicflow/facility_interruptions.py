"""Assess non-clinical facility interruptions against room operations."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .models import DomainError, clean_code, parse_time


class FacilityService(StrEnum):
    POWER = "power"
    WATER = "water"
    NETWORK = "network"
    ACCESS = "access"


@dataclass(frozen=True, slots=True)
class FacilityInterruption:
    interruption_id: str
    clinic_id: str
    service: FacilityService
    starts_at: str
    ends_at: str
    affected_room_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FacilityRoomUse:
    booking_id: str
    clinic_id: str
    room_id: str
    starts_at: str
    ends_at: str
    network_required: bool
    accessible_route_required: bool


@dataclass(frozen=True, slots=True)
class FacilityImpactDecision:
    booking_id: str
    interruption_id: str
    action: str
    reason: str


def assess_facility_interruptions(
    interruptions: list[FacilityInterruption], bookings: list[FacilityRoomUse]
) -> list[FacilityImpactDecision]:
    """Return relocation or contingency actions for overlapping room uses."""
    interruption_ids: set[str] = set()
    normalized_interruptions: list[tuple[FacilityInterruption, datetime, datetime, set[str]]] = []
    for interruption in interruptions:
        interruption_id = clean_code(interruption.interruption_id, "interruption id")
        if interruption_id.casefold() in interruption_ids:
            raise DomainError(f"duplicate facility interruption: {interruption_id}")
        interruption_ids.add(interruption_id.casefold())
        clinic_id = clean_code(interruption.clinic_id, "interruption clinic id")
        if not isinstance(interruption.service, FacilityService):
            raise DomainError("facility interruption service is invalid")
        start = parse_time(interruption.starts_at, "interruption starts_at")
        end = parse_time(interruption.ends_at, "interruption ends_at")
        if end <= start:
            raise DomainError("interruption ends_at must follow starts_at")
        rooms = {clean_code(room_id, "affected room id") for room_id in interruption.affected_room_ids}
        if not rooms:
            raise DomainError("facility interruption requires an affected room")
        normalized_interruption = FacilityInterruption(
            interruption_id,
            clinic_id,
            interruption.service,
            interruption.starts_at,
            interruption.ends_at,
            tuple(sorted(rooms)),
        )
        normalized_interruptions.append((normalized_interruption, start, end, rooms))
    booking_ids: set[str] = set()
    decisions: list[FacilityImpactDecision] = []
    for booking in bookings:
        booking_id = clean_code(booking.booking_id, "facility booking id")
        if booking_id.casefold() in booking_ids:
            raise DomainError(f"duplicate facility booking: {booking_id}")
        booking_ids.add(booking_id.casefold())
        clinic_id = clean_code(booking.clinic_id, "booking clinic id")
        room_id = clean_code(booking.room_id, "booking room id")
        start = parse_time(booking.starts_at, "booking starts_at")
        end = parse_time(booking.ends_at, "booking ends_at")
        if end <= start:
            raise DomainError("booking ends_at must follow starts_at")
        for interruption, outage_start, outage_end, rooms in normalized_interruptions:
            if (
                interruption.clinic_id != clinic_id
                or room_id not in rooms
                or start >= outage_end
                or end <= outage_start
            ):
                continue
            action, reason = _impact(interruption.service, booking)
            decisions.append(FacilityImpactDecision(booking_id, interruption.interruption_id, action, reason))
    return sorted(decisions, key=lambda item: (item.booking_id, item.interruption_id))


def _impact(service: FacilityService, booking: FacilityRoomUse) -> tuple[str, str]:
    if service in {FacilityService.POWER, FacilityService.WATER}:
        return "relocate", f"{service.value} interruption makes the room unavailable"
    if service is FacilityService.NETWORK and booking.network_required:
        return "relocate", "booking requires unavailable network service"
    if service is FacilityService.ACCESS and booking.accessible_route_required:
        return "relocate", "booking requires the interrupted accessible route"
    return "contingency", f"continue with documented {service.value} contingency"
