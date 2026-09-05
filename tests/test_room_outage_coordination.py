from datetime import UTC, datetime, timedelta

import pytest

from clinicflow.room_outage_coordination import (
    AppointmentImpact,
    OutageCause,
    OutageState,
    RelocationOption,
    RestorationCheck,
    RoomOutage,
    RoomOutageBoard,
)

NOW = datetime(2026, 9, 5, 8, tzinfo=UTC)


def test_relocates_appointments_and_gates_room_restoration() -> None:
    board = RoomOutageBoard()
    board.open_outage(
        RoomOutage(
            "outage",
            "room-1",
            "site",
            OutageCause.UTILITIES,
            NOW,
            "facilities",
            NOW + timedelta(hours=3),
            affected_appointment_ids=("appointment",),
        )
    )
    board.contain("outage", NOW + timedelta(minutes=5), "Room isolated")
    board.start_repair("outage", NOW + timedelta(minutes=10))
    decisions = board.plan_relocations(
        "outage",
        (AppointmentImpact("appointment", NOW + timedelta(hours=1), NOW + timedelta(hours=2), ("accessible",), True),),
        (RelocationOption("room-2", "site", NOW, NOW + timedelta(days=1), ("accessible",), 5),),
    )
    assert decisions[0].room_id == "room-2"
    board.record_check(
        RestorationCheck("check", "outage", "utilities", NOW + timedelta(hours=2), "engineer", True, "evidence")
    )
    restored = board.restore("outage", NOW + timedelta(hours=2), ("utilities",))
    assert restored.state is OutageState.RESTORED


def test_blocks_restoration_after_failed_check() -> None:
    board = RoomOutageBoard()
    board.open_outage(RoomOutage("outage", "room", "site", OutageCause.SAFETY, NOW, "staff", NOW + timedelta(hours=1)))
    board.contain("outage", NOW, "Access locked")
    board.start_repair("outage", NOW)
    board.record_check(RestorationCheck("check", "outage", "safety", NOW, "officer", False, "ev"))
    with pytest.raises(ValueError, match="not ready"):
        board.restore("outage", NOW + timedelta(minutes=30), ("safety",))
    assert board.overdue(NOW + timedelta(hours=2))[0].outage_id == "outage"
