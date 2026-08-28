from dataclasses import replace

import pytest

from clinicflow import DomainError, PreparationRequest, RoomReadiness, assess_room_preparation


def room(identifier: str = "room-a") -> RoomReadiness:
    return RoomReadiness(
        identifier,
        "2026-09-02T08:00:00+02:00",
        ("monitor", "wheelchair"),
    )


def request(identifier: str = "visit-a") -> PreparationRequest:
    return PreparationRequest(
        identifier,
        "room-a",
        "2026-09-02T10:00:00+02:00",
        ("monitor",),
        30,
    )


def test_reports_ready_room_and_setup_deadline() -> None:
    [assessment] = assess_room_preparation(
        [request()],
        [room()],
        "2026-09-02T09:00:00+02:00",
    )
    assert assessment.ready is True
    assert assessment.setup_must_start_at == "2026-09-02T09:30:00+02:00"
    assert assessment.missing_assets == ()


def test_prioritizes_blocked_rooms_and_reports_missing_assets() -> None:
    blocked = replace(room(), blocked_until="2026-09-02T09:45:00+02:00")
    missing = replace(request(), required_assets=("monitor", "infusion-pump"))
    [assessment] = assess_room_preparation(
        [missing],
        [blocked],
        "2026-09-02T09:00:00+02:00",
    )
    assert assessment.ready is False
    assert assessment.missing_assets == ("infusion-pump",)
    assert assessment.blocking_reasons == ("room_block_overlaps_setup", "assets_missing")


def test_rejects_casefold_duplicates_unknown_rooms_and_duplicate_assets() -> None:
    with pytest.raises(DomainError, match="duplicate room readiness"):
        assess_room_preparation([request()], [room("Room-A"), room("room-a")], "2026-09-02T09:00:00+02:00")
    with pytest.raises(DomainError, match="unknown preparation room"):
        assess_room_preparation(
            [replace(request(), room_id="room-missing")],
            [room()],
            "2026-09-02T09:00:00+02:00",
        )
    with pytest.raises(DomainError, match="duplicate required asset"):
        assess_room_preparation(
            [replace(request(), required_assets=("Monitor", "monitor"))],
            [room()],
            "2026-09-02T09:00:00+02:00",
        )
