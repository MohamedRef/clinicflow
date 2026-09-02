"""Schedule non-clinical patient shuttle arrivals against bay capacity."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class ShuttleArrival:
    trip_id: str
    clinic_id: str
    arrival_minute: int
    dwell_minutes: int
    passengers: int
    priority: int


@dataclass(frozen=True, slots=True)
class ShuttleBay:
    bay_id: str
    clinic_id: str
    passenger_limit: int
    opens_minute: int
    closes_minute: int


@dataclass(frozen=True, slots=True)
class ShuttleBayAssignment:
    trip_id: str
    bay_id: str | None
    assigned: bool
    reason: str


def schedule_shuttle_arrivals(arrivals: list[ShuttleArrival], bays: list[ShuttleBay]) -> list[ShuttleBayAssignment]:
    """Reserve a compatible bay without double-booking its dwell interval."""
    normalized_bays: dict[str, ShuttleBay] = {}
    for bay in bays:
        bay_id = clean_code(bay.bay_id, "shuttle bay id")
        clinic_id = clean_code(bay.clinic_id, "shuttle bay clinic id")
        if bay_id in normalized_bays:
            raise DomainError(f"duplicate shuttle bay: {bay_id}")
        if bay.passenger_limit < 1 or bay.opens_minute < 0 or bay.closes_minute <= bay.opens_minute:
            raise DomainError("shuttle bay capacity or timing is invalid")
        normalized_bays[bay_id] = ShuttleBay(
            bay_id, clinic_id, bay.passenger_limit, bay.opens_minute, bay.closes_minute
        )

    normalized_arrivals: list[ShuttleArrival] = []
    trip_ids: set[str] = set()
    for arrival in arrivals:
        trip_id = clean_code(arrival.trip_id, "shuttle trip id")
        clinic_id = clean_code(arrival.clinic_id, "shuttle arrival clinic id")
        if trip_id in trip_ids:
            raise DomainError(f"duplicate shuttle trip: {trip_id}")
        if arrival.arrival_minute < 0 or arrival.dwell_minutes < 1 or arrival.passengers < 1 or arrival.priority < 0:
            raise DomainError("shuttle arrival is invalid")
        trip_ids.add(trip_id)
        normalized_arrivals.append(
            ShuttleArrival(
                trip_id, clinic_id, arrival.arrival_minute, arrival.dwell_minutes, arrival.passengers, arrival.priority
            )
        )

    reservations: dict[str, list[tuple[int, int]]] = {bay_id: [] for bay_id in normalized_bays}
    assignments: list[ShuttleBayAssignment] = []
    for arrival in sorted(normalized_arrivals, key=lambda item: (-item.priority, item.arrival_minute, item.trip_id)):
        end = arrival.arrival_minute + arrival.dwell_minutes
        selected = next(
            (
                bay_id
                for bay_id, bay in sorted(normalized_bays.items())
                if bay.clinic_id == arrival.clinic_id
                and bay.passenger_limit >= arrival.passengers
                and bay.opens_minute <= arrival.arrival_minute
                and end <= bay.closes_minute
                and all(
                    end <= start or arrival.arrival_minute >= booked_end for start, booked_end in reservations[bay_id]
                )
            ),
            None,
        )
        if selected is None:
            assignments.append(ShuttleBayAssignment(arrival.trip_id, None, False, "no_compatible_bay"))
        else:
            reservations[selected].append((arrival.arrival_minute, end))
            assignments.append(ShuttleBayAssignment(arrival.trip_id, selected, True, "assigned"))
    return assignments
