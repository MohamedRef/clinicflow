"""Coordinate non-clinical transport arrivals for appointments."""

from dataclasses import dataclass
from datetime import datetime

from clinicflow.models import DomainError


@dataclass(frozen=True, slots=True)
class AppointmentTransportRequest:
    appointment_id: str
    pickup_zone: str
    appointment_at: datetime
    passengers: int
    wheelchair_spaces: int


@dataclass(frozen=True, slots=True)
class TransportVehicle:
    vehicle_id: str
    pickup_zone: str
    passenger_capacity: int
    wheelchair_capacity: int


@dataclass(frozen=True, slots=True)
class AppointmentTransportPlan:
    appointment_id: str
    vehicle_id: str | None
    state: str


def plan_appointment_transport(
    requests: list[AppointmentTransportRequest], vehicles: list[TransportVehicle]
) -> list[AppointmentTransportPlan]:
    """Assign each request to a compatible vehicle once."""
    available: dict[str, TransportVehicle] = {}
    for vehicle in vehicles:
        key = vehicle.vehicle_id.strip().casefold()
        if not key or key in available or vehicle.passenger_capacity < 1 or vehicle.wheelchair_capacity < 0:
            raise DomainError("invalid or duplicate transport vehicle")
        available[key] = vehicle
    seen: set[str] = set()
    plans: list[AppointmentTransportPlan] = []
    for request in sorted(requests, key=lambda row: (row.appointment_at, row.appointment_id)):
        appointment = request.appointment_id.strip()
        if (
            not appointment
            or appointment.casefold() in seen
            or request.appointment_at.tzinfo is None
            or request.passengers < 1
            or request.wheelchair_spaces < 0
            or request.wheelchair_spaces > request.passengers
        ):
            raise DomainError("invalid or duplicate transport request")
        seen.add(appointment.casefold())
        selected = next(
            (
                key
                for key, vehicle in available.items()
                if vehicle.pickup_zone.casefold() == request.pickup_zone.strip().casefold()
                and vehicle.passenger_capacity >= request.passengers
                and vehicle.wheelchair_capacity >= request.wheelchair_spaces
            ),
            None,
        )
        plans.append(
            AppointmentTransportPlan(
                appointment,
                available[selected].vehicle_id if selected else None,
                "assigned" if selected else "capacity_required",
            )
        )
        if selected:
            del available[selected]
    return plans
