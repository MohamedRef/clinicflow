from datetime import UTC, datetime, timedelta

from clinicflow import RoomAccessEvent, RoomAccessRequirement, assess_room_access_logs


def test_reports_outside_window_and_missing_escort() -> None:
    start = datetime(2026, 9, 4, 10, tzinfo=UTC)
    rows = assess_room_access_logs(
        [RoomAccessRequirement("room", "staff", start, start + timedelta(hours=1), True)],
        [RoomAccessEvent("event", "room", "staff", start + timedelta(hours=2), False)],
    )
    assert rows[0].blockers == ("outside_access_window", "escort_missing")


def test_reports_missing_grant() -> None:
    now = datetime(2026, 9, 4, 10, tzinfo=UTC)
    rows = assess_room_access_logs([], [RoomAccessEvent("event", "room", "staff", now, True)])
    assert rows[0].blockers == ("grant_missing",)
