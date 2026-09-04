from datetime import UTC, datetime, timedelta

from clinicflow import RoomKeyHandoff, assess_room_key_handoffs


def test_reports_room_keys_outstanding_across_shifts() -> None:
    now = datetime(2026, 9, 4, 12, tzinfo=UTC)
    rows = assess_room_key_handoffs(
        [
            RoomKeyHandoff("overdue", "r1", "staff", now - timedelta(hours=13), None),
            RoomKeyHandoff("returned", "r2", "staff", now - timedelta(hours=2), now - timedelta(hours=1)),
        ],
        as_of=now,
    )
    assert [row.state for row in rows] == ["overdue", "returned"]
