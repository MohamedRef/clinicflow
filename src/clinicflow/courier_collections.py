"""Schedule accountable non-clinical courier collections from clinic desks."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class CourierCollectionRequest:
    collection_id: str
    clinic_id: str
    package_count: int
    earliest_at: str
    latest_at: str
    requires_cold_transport: bool


@dataclass(frozen=True, slots=True)
class CourierWindow:
    window_id: str
    clinic_id: str
    starts_at: str
    ends_at: str
    package_capacity: int
    cold_transport: bool


@dataclass(frozen=True, slots=True)
class CourierCollectionAssignment:
    collection_id: str
    window_id: str | None
    assigned: bool
    reason: str


def schedule_courier_collections(
    requests: list[CourierCollectionRequest], windows: list[CourierWindow]
) -> list[CourierCollectionAssignment]:
    """Allocate earliest compatible collection capacity, preserving package counts."""
    remaining: dict[str, int] = {}
    normalized_windows: list[tuple[CourierWindow, datetime, datetime]] = []
    window_ids: set[str] = set()
    for window in windows:
        window_id = clean_code(window.window_id, "courier window id")
        if window_id.casefold() in window_ids:
            raise DomainError(f"duplicate courier window: {window_id}")
        window_ids.add(window_id.casefold())
        clinic_id = clean_code(window.clinic_id, "courier clinic id")
        start = parse_time(window.starts_at, "courier starts_at")
        end = parse_time(window.ends_at, "courier ends_at")
        if end <= start or end - start > timedelta(hours=8):
            raise DomainError("courier window requires a positive duration of at most eight hours")
        if (
            isinstance(window.package_capacity, bool)
            or not isinstance(window.package_capacity, int)
            or window.package_capacity < 1
        ):
            raise DomainError("courier package capacity must be a positive integer")
        normalized = CourierWindow(
            window_id, clinic_id, window.starts_at, window.ends_at, window.package_capacity, window.cold_transport
        )
        normalized_windows.append((normalized, start, end))
        remaining[window_id] = window.package_capacity
    request_ids: set[str] = set()
    normalized_requests: list[tuple[CourierCollectionRequest, datetime, datetime]] = []
    for request in requests:
        collection_id = clean_code(request.collection_id, "collection id")
        if collection_id.casefold() in request_ids:
            raise DomainError(f"duplicate courier collection: {collection_id}")
        request_ids.add(collection_id.casefold())
        clinic_id = clean_code(request.clinic_id, "collection clinic id")
        earliest = parse_time(request.earliest_at, "collection earliest_at")
        latest = parse_time(request.latest_at, "collection latest_at")
        if latest <= earliest:
            raise DomainError("collection latest_at must follow earliest_at")
        if (
            isinstance(request.package_count, bool)
            or not isinstance(request.package_count, int)
            or request.package_count < 1
        ):
            raise DomainError("collection package count must be a positive integer")
        normalized_requests.append(
            (
                CourierCollectionRequest(
                    collection_id,
                    clinic_id,
                    request.package_count,
                    request.earliest_at,
                    request.latest_at,
                    request.requires_cold_transport,
                ),
                earliest,
                latest,
            )
        )
    normalized_requests.sort(
        key=lambda row: (row[2], not row[0].requires_cold_transport, -row[0].package_count, row[0].collection_id)
    )
    assignments: list[CourierCollectionAssignment] = []
    for request, earliest, latest in normalized_requests:
        candidates = [
            row
            for row in normalized_windows
            if row[0].clinic_id == request.clinic_id
            and row[1] >= earliest
            and row[2] <= latest
            and remaining[row[0].window_id] >= request.package_count
            and (not request.requires_cold_transport or row[0].cold_transport)
        ]
        candidates.sort(key=lambda row: (row[1], row[0].window_id))
        if not candidates:
            assignments.append(
                CourierCollectionAssignment(request.collection_id, None, False, "no compatible courier capacity")
            )
            continue
        selected = candidates[0][0]
        remaining[selected.window_id] -= request.package_count
        assignments.append(
            CourierCollectionAssignment(
                request.collection_id, selected.window_id, True, "earliest compatible courier window"
            )
        )
    return assignments
