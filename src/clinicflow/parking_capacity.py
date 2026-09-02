"""Allocate limited clinic parking capacity to appointment arrivals."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class ParkingArrival:
    appointment_id: str
    clinic_id: str
    arrival_minute: int
    departure_minute: int
    accessible_space_required: bool = False


@dataclass(frozen=True, slots=True)
class ClinicParkingCapacity:
    clinic_id: str
    standard_spaces: int
    accessible_spaces: int


@dataclass(frozen=True, slots=True)
class ParkingAllocation:
    appointment_id: str
    space_type: str | None
    allocated: bool


def allocate_clinic_parking(
    arrivals: list[ParkingArrival], capacities: list[ClinicParkingCapacity]
) -> list[ParkingAllocation]:
    """Allocate spaces without allowing overlapping appointments to reuse capacity."""
    configured: dict[str, ClinicParkingCapacity] = {}
    for capacity in capacities:
        clinic_id = clean_code(capacity.clinic_id, "parking clinic id")
        if clinic_id in configured:
            raise DomainError(f"duplicate parking capacity: {clinic_id}")
        if capacity.standard_spaces < 0 or capacity.accessible_spaces < 0:
            raise DomainError("parking capacities cannot be negative")
        configured[clinic_id] = capacity

    seen: set[str] = set()
    normalized: list[ParkingArrival] = []
    for arrival in arrivals:
        appointment_id = clean_code(arrival.appointment_id, "parking appointment id")
        clinic_id = clean_code(arrival.clinic_id, "parking clinic id")
        if appointment_id in seen:
            raise DomainError(f"duplicate parking appointment: {appointment_id}")
        if (
            clinic_id not in configured
            or arrival.arrival_minute < 0
            or arrival.departure_minute <= arrival.arrival_minute
        ):
            raise DomainError("parking arrival must reference a configured clinic and valid interval")
        seen.add(appointment_id)
        normalized.append(arrival)

    active: dict[str, dict[str, list[int]]] = {
        clinic_id: {"standard": [], "accessible": []} for clinic_id in configured
    }
    allocations: list[ParkingAllocation] = []
    for arrival in sorted(
        normalized, key=lambda item: (item.arrival_minute, not item.accessible_space_required, item.appointment_id)
    ):
        clinic_id = arrival.clinic_id.strip()
        for departures in active[clinic_id].values():
            departures[:] = [minute for minute in departures if minute > arrival.arrival_minute]
        capacity = configured[clinic_id]
        if arrival.accessible_space_required:
            available = len(active[clinic_id]["accessible"]) < capacity.accessible_spaces
            space_type = "accessible" if available else None
        elif len(active[clinic_id]["standard"]) < capacity.standard_spaces:
            available, space_type = True, "standard"
        else:
            available = len(active[clinic_id]["accessible"]) < capacity.accessible_spaces
            space_type = "accessible" if available else None
        if space_type:
            active[clinic_id][space_type].append(arrival.departure_minute)
        allocations.append(ParkingAllocation(arrival.appointment_id, space_type, available))
    return allocations
