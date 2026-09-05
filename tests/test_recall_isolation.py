import pytest

from clinicflow.recall_isolation import (
    RecallIsolationStatus,
    RecallRoomPosition,
    assess_recall_isolation,
)


def test_escalates_unaccounted_units_before_other_isolation_gaps() -> None:
    findings = assess_recall_isolation(
        [
            RecallRoomPosition("lot-a", "room-2", 8, 8, 980, False),
            RecallRoomPosition("lot-a", "room-1", 10, 7, 970, True),
            RecallRoomPosition("lot-b", "room-3", 4, 4, 990, True),
        ],
        review_minute=1_000,
        maximum_sweep_age_minutes=60,
    )
    assert [(item.room_id, item.status) for item in findings] == [
        ("room-1", RecallIsolationStatus.ESCALATE),
        ("room-2", RecallIsolationStatus.BLOCKED),
        ("room-3", RecallIsolationStatus.ISOLATED),
    ]
    assert findings[0].units_unaccounted == 3


def test_blocks_missing_and_stale_room_sweeps() -> None:
    findings = assess_recall_isolation(
        [
            RecallRoomPosition("lot-a", "missing", 0, 0, None, True),
            RecallRoomPosition("lot-a", "stale", 2, 2, 800, True),
        ],
        review_minute=1_000,
        maximum_sweep_age_minutes=100,
    )
    assert all(item.status is RecallIsolationStatus.BLOCKED for item in findings)
    assert findings[0].reasons == ("room sweep missing",)
    assert findings[1].reasons == ("room sweep is stale",)


def test_rejects_repeated_rooms_and_impossible_counts() -> None:
    row = RecallRoomPosition("lot", "room", 2, 2, 900, True)
    with pytest.raises(ValueError, match="duplicate"):
        assess_recall_isolation(
            [row, RecallRoomPosition(" LOT ", " ROOM ", 2, 2, 900, True)],
            review_minute=1_000,
            maximum_sweep_age_minutes=60,
        )
    with pytest.raises(ValueError, match="quantities"):
        assess_recall_isolation(
            [RecallRoomPosition("lot", "room", 2, 3, 900, True)],
            review_minute=1_000,
            maximum_sweep_age_minutes=60,
        )
