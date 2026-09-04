import pytest

from clinicflow import AppointmentPacket, assess_appointment_packets
from clinicflow.models import DomainError


def test_prioritizes_blocked_and_incomplete_appointment_packets() -> None:
    rows = assess_appointment_packets(
        [
            AppointmentPacket("ready", ("id",), ("ID",), True, "room-a"),
            AppointmentPacket("incomplete", ("id", "consent"), ("id",), True, "room-b"),
            AppointmentPacket("blocked", ("id",), ("id",), False, None),
        ]
    )
    assert [row.state for row in rows] == ["blocked", "incomplete", "ready"]
    assert rows[0].defects == ("contact_unconfirmed", "room_unassigned")
    assert rows[1].missing_documents == ("consent",)


def test_rejects_duplicate_and_unexpected_packet_documents() -> None:
    valid = AppointmentPacket("appointment", ("id",), ("id",), True, "room")
    with pytest.raises(DomainError, match="duplicate"):
        assess_appointment_packets([valid, AppointmentPacket(" APPOINTMENT ", ("id",), ("id",), True, "room")])
    with pytest.raises(DomainError, match="at least one"):
        assess_appointment_packets([AppointmentPacket("appointment", (), (), True, "room")])
    with pytest.raises(DomainError, match="unexpected"):
        assess_appointment_packets([AppointmentPacket("appointment", ("id",), ("id", "extra"), True, "room")])
    with pytest.raises(DomainError, match="unique"):
        assess_appointment_packets([AppointmentPacket("appointment", ("id", "ID"), ("id",), True, "room")])
