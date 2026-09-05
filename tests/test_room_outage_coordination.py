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


def test_reports_unresolved_relocation_and_validates_lifecycle() -> None:
    board = RoomOutageBoard()
    outage = RoomOutage(
        "outage",
        "room",
        "site",
        OutageCause.ACCESS,
        NOW,
        "staff",
        NOW + timedelta(hours=2),
        affected_appointment_ids=("appointment",),
    )
    board.open_outage(outage)
    with pytest.raises(ValueError, match="already has active"):
        board.open_outage(
            RoomOutage("other", "ROOM", "site", OutageCause.ACCESS, NOW, "staff", NOW + timedelta(hours=2))
        )
    board.contain("outage", NOW, "Door isolated")
    board.start_repair("outage", NOW)
    decisions = board.plan_relocations(
        "outage",
        (AppointmentImpact("appointment", NOW + timedelta(hours=1), NOW + timedelta(hours=2), ("accessible",), True),),
        (RelocationOption("far", "site", NOW, NOW + timedelta(days=1), ("accessible",), 30),),
    )
    assert decisions[0].ready is False
    board.record_check(RestorationCheck("check", "outage", "access", NOW, "officer", True, "evidence"))
    ready, blockers = board.restoration_readiness("outage", ("access", "cleaning"))
    assert ready is False
    assert "missing restoration check: cleaning" in blockers
    assert "appointment relocation remains unresolved" in blockers


def test_rejects_unknown_impacts_and_invalid_checks() -> None:
    board = RoomOutageBoard()
    board.open_outage(
        RoomOutage("outage", "room", "site", OutageCause.EQUIPMENT, NOW, "staff", NOW + timedelta(hours=2))
    )
    with pytest.raises(ValueError, match="not registered"):
        board.plan_relocations("outage", (AppointmentImpact("unknown", NOW, NOW + timedelta(hours=1), (), False),), ())
    with pytest.raises(ValueError, match="active repair"):
        board.record_check(RestorationCheck("check", "outage", "equipment", NOW, "officer", True, "evidence"))
    with pytest.raises(KeyError, match="unknown room outage"):
        board.overdue(NOW)
        board.restore("missing", NOW, ())


def test_validates_outage_and_relocation_boundaries() -> None:
    board = RoomOutageBoard()
    with pytest.raises(ValueError, match="must follow"):
        board.open_outage(RoomOutage("outage", "room", "site", OutageCause.ACCESS, NOW, "staff", NOW))
    board.open_outage(
        RoomOutage(
            "outage",
            "room",
            "site",
            OutageCause.ACCESS,
            NOW,
            "staff",
            NOW + timedelta(hours=1),
            affected_appointment_ids=("appointment",),
        )
    )
    with pytest.raises(ValueError, match="requires contained"):
        board.start_repair("outage", NOW)
    board.contain("outage", NOW, "Isolated")
    board.start_repair("outage", NOW)
    with pytest.raises(ValueError, match="availability"):
        board.plan_relocations(
            "outage",
            (AppointmentImpact("appointment", NOW, NOW + timedelta(hours=1), (), False),),
            (RelocationOption("room-2", "site", NOW, NOW, (), 0),),
        )
    board.record_check(RestorationCheck("check", "outage", "access", NOW, "officer", True, "evidence"))
    with pytest.raises(ValueError, match="duplicate"):
        board.record_check(RestorationCheck("check", "outage", "access", NOW, "officer", True, "evidence"))
