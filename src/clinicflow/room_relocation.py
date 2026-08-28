"""Priority-aware appointment relocation during room outages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import DomainError, clean_code, clean_codes, parse_time


@dataclass(frozen=True, slots=True)
class OutageAppointment:
    appointment_id: str
    current_room_id: str
    starts_at: str
    ends_at: str
    required_capabilities: set[str]
    priority: int


@dataclass(frozen=True, slots=True)
class RelocationRoom:
    room_id: str
    capabilities: set[str]
    available_from: str
    available_until: str


@dataclass(frozen=True, slots=True)
class RoomBooking:
    booking_id: str
    room_id: str
    starts_at: str
    ends_at: str


@dataclass(frozen=True, slots=True)
class RoomRelocation:
    appointment_id: str
    replacement_room_id: str | None
    relocated: bool
    reason: str


def _window(starts_at: str, ends_at: str, label: str) -> tuple[datetime, datetime]:
    starts = parse_time(starts_at, f"{label} starts_at")
    ends = parse_time(ends_at, f"{label} ends_at")
    if ends <= starts:
        raise DomainError(f"{label} must have a positive duration")
    return starts, ends


def _overlaps(
    starts_at: datetime,
    ends_at: datetime,
    occupied_starts_at: datetime,
    occupied_ends_at: datetime,
) -> bool:
    return starts_at < occupied_ends_at and occupied_starts_at < ends_at


def relocate_room_outages(
    appointments: list[OutageAppointment],
    rooms: list[RelocationRoom],
    existing_bookings: list[RoomBooking] | None = None,
) -> list[RoomRelocation]:
    """Relocate affected appointments without capability or schedule conflicts."""
    normalized_rooms: dict[str, tuple[RelocationRoom, datetime, datetime]] = {}
    for room in rooms:
        room_id = clean_code(room.room_id, "relocation room id")
        if room_id in normalized_rooms:
            raise DomainError(f"duplicate relocation room id: {room_id}")
        available_from, available_until = _window(room.available_from, room.available_until, "room availability")
        normalized_rooms[room_id] = (
            RelocationRoom(
                room_id,
                clean_codes(room.capabilities, "room capability"),
                room.available_from,
                room.available_until,
            ),
            available_from,
            available_until,
        )

    occupied: dict[str, list[tuple[datetime, datetime]]] = {room_id: [] for room_id in normalized_rooms}
    seen_bookings: set[str] = set()
    for booking in existing_bookings or []:
        booking_id = clean_code(booking.booking_id, "room booking id")
        if booking_id in seen_bookings:
            raise DomainError(f"duplicate room booking id: {booking_id}")
        seen_bookings.add(booking_id)
        room_id = clean_code(booking.room_id, "booked room id")
        if room_id not in normalized_rooms:
            raise DomainError(f"booking references unknown relocation room: {room_id}")
        starts_at, ends_at = _window(booking.starts_at, booking.ends_at, "room booking")
        occupied[room_id].append((starts_at, ends_at))

    normalized_appointments: list[tuple[OutageAppointment, datetime, datetime]] = []
    seen_appointments: set[str] = set()
    for appointment in appointments:
        appointment_id = clean_code(appointment.appointment_id, "outage appointment id")
        if appointment_id in seen_appointments:
            raise DomainError(f"duplicate outage appointment id: {appointment_id}")
        seen_appointments.add(appointment_id)
        starts_at, ends_at = _window(appointment.starts_at, appointment.ends_at, "outage appointment")
        if (
            isinstance(appointment.priority, bool)
            or not isinstance(appointment.priority, int)
            or not 1 <= appointment.priority <= 5
        ):
            raise DomainError("appointment priority must be an integer from 1 through 5")
        normalized_appointments.append(
            (
                OutageAppointment(
                    appointment_id,
                    clean_code(appointment.current_room_id, "current room id"),
                    appointment.starts_at,
                    appointment.ends_at,
                    clean_codes(appointment.required_capabilities, "required room capability"),
                    appointment.priority,
                ),
                starts_at,
                ends_at,
            )
        )

    relocations: list[RoomRelocation] = []
    for appointment, starts_at, ends_at in sorted(
        normalized_appointments,
        key=lambda item: (-item[0].priority, item[1], item[0].appointment_id),
    ):
        eligible: list[str] = []
        for room_id, (room, available_from, available_until) in normalized_rooms.items():
            if room_id == appointment.current_room_id:
                continue
            if not appointment.required_capabilities <= room.capabilities:
                continue
            if starts_at < available_from or ends_at > available_until:
                continue
            if any(
                _overlaps(starts_at, ends_at, booked_start, booked_end)
                for booked_start, booked_end in occupied[room_id]
            ):
                continue
            eligible.append(room_id)
        if not eligible:
            relocations.append(RoomRelocation(appointment.appointment_id, None, False, "no capable conflict-free room"))
            continue
        selected = min(eligible, key=lambda room_id: (len(occupied[room_id]), room_id))
        occupied[selected].append((starts_at, ends_at))
        relocations.append(RoomRelocation(appointment.appointment_id, selected, True, "replacement room assigned"))
    return relocations
