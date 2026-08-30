import pytest

from clinicflow import CourierCollectionRequest, CourierWindow, DomainError, schedule_courier_collections


def test_schedules_cold_collections_into_capable_windows() -> None:
    windows = [
        CourierWindow("ambient", "clinic-a", "2026-08-30T10:00:00Z", "2026-08-30T11:00:00Z", 4, False),
        CourierWindow("cold", "clinic-a", "2026-08-30T11:00:00Z", "2026-08-30T12:00:00Z", 2, True),
    ]
    requests = [
        CourierCollectionRequest("cold-request", "clinic-a", 2, "2026-08-30T09:00:00Z", "2026-08-30T13:00:00Z", True),
        CourierCollectionRequest(
            "ambient-request", "clinic-a", 3, "2026-08-30T09:00:00Z", "2026-08-30T13:00:00Z", False
        ),
    ]
    assignments = schedule_courier_collections(requests, windows)
    assert [(item.collection_id, item.window_id) for item in assignments] == [
        ("cold-request", "cold"),
        ("ambient-request", "ambient"),
    ]


def test_rejects_duplicate_collection_and_window_ids() -> None:
    request = CourierCollectionRequest("same", "clinic", 1, "2026-08-30T09:00:00Z", "2026-08-30T10:00:00Z", False)
    with pytest.raises(DomainError, match="duplicate courier collection"):
        schedule_courier_collections([request, request], [])
    window = CourierWindow("same", "clinic", "2026-08-30T09:00:00Z", "2026-08-30T10:00:00Z", 1, False)
    with pytest.raises(DomainError, match="duplicate courier window"):
        schedule_courier_collections([], [window, window])
