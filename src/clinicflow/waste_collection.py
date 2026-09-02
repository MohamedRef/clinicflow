"""Schedule segregated clinic waste collections before storage limits."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class ClinicWasteDemand:
    collection_id: str
    clinic_id: str
    waste_stream: str
    container_count: int
    ready_minute: int
    deadline_minute: int
    service_minutes: int
    priority: int


@dataclass(frozen=True, slots=True)
class WasteCourierShift:
    courier_id: str
    clinic_id: str
    accepted_streams: tuple[str, ...]
    container_capacity: int
    starts_minute: int
    ends_minute: int


@dataclass(frozen=True, slots=True)
class WasteCollectionAssignment:
    collection_id: str
    courier_id: str | None
    start_minute: int | None
    end_minute: int | None
    assigned: bool


def schedule_waste_collections(
    demands: list[ClinicWasteDemand],
    shifts: list[WasteCourierShift],
) -> list[WasteCollectionAssignment]:
    """Assign priority collections to compatible courier shifts."""
    shift_ids: set[str] = set()
    availability: dict[str, tuple[WasteCourierShift, int]] = {}
    for shift in shifts:
        courier_id = clean_code(shift.courier_id, "waste courier id")
        clinic_id = clean_code(shift.clinic_id, "waste courier clinic id")
        streams = tuple(clean_code(item, "accepted waste stream") for item in shift.accepted_streams)
        if (
            courier_id in shift_ids
            or not streams
            or len(set(streams)) != len(streams)
            or shift.container_capacity < 1
            or shift.starts_minute < 0
            or shift.ends_minute <= shift.starts_minute
        ):
            raise DomainError("waste courier shift is duplicated or invalid")
        shift_ids.add(courier_id)
        normalized = WasteCourierShift(
            courier_id,
            clinic_id,
            streams,
            shift.container_capacity,
            shift.starts_minute,
            shift.ends_minute,
        )
        availability[courier_id] = (normalized, shift.starts_minute)
    seen: set[str] = set()
    normalized_demands: list[ClinicWasteDemand] = []
    for demand in demands:
        collection_id = clean_code(demand.collection_id, "waste collection id")
        clinic_id = clean_code(demand.clinic_id, "waste collection clinic id")
        stream = clean_code(demand.waste_stream, "waste collection stream")
        if (
            collection_id in seen
            or demand.container_count < 1
            or demand.ready_minute < 0
            or demand.deadline_minute <= demand.ready_minute
            or demand.service_minutes < 1
            or demand.priority < 0
        ):
            raise DomainError("waste collection demand is duplicated or invalid")
        seen.add(collection_id)
        normalized_demands.append(
            ClinicWasteDemand(
                collection_id,
                clinic_id,
                stream,
                demand.container_count,
                demand.ready_minute,
                demand.deadline_minute,
                demand.service_minutes,
                demand.priority,
            )
        )
    assignments: list[WasteCollectionAssignment] = []
    for demand in sorted(
        normalized_demands,
        key=lambda item: (-item.priority, item.deadline_minute, item.collection_id),
    ):
        candidates: list[tuple[int, str]] = []
        for courier_id, (shift, next_minute) in availability.items():
            start = max(next_minute, demand.ready_minute)
            if (
                shift.clinic_id == demand.clinic_id
                and demand.waste_stream in shift.accepted_streams
                and shift.container_capacity >= demand.container_count
                and start + demand.service_minutes <= min(demand.deadline_minute, shift.ends_minute)
            ):
                candidates.append((start, courier_id))
        if not candidates:
            assignments.append(WasteCollectionAssignment(demand.collection_id, None, None, None, False))
            continue
        start, courier_id = min(candidates)
        shift, _ = availability[courier_id]
        end = start + demand.service_minutes
        availability[courier_id] = (shift, end)
        assignments.append(WasteCollectionAssignment(demand.collection_id, courier_id, start, end, True))
    return assignments
