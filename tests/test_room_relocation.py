import pytest

from clinicflow import (
    DomainError,
    OutageAppointment,
    RelocationRoom,
    RoomBooking,
    RoomRelocation,
    relocate_room_outages,
)


def appointment(identifier: str, starts_at: str, priority: int, capabilities: set[str]) -> OutageAppointment:
    return OutageAppointment(
        identifier,
        "outage-room",
        starts_at,
        starts_at.replace(":00:00", ":45:00"),
        capabilities,
        priority,
    )


def room(identifier: str, capabilities: set[str]) -> RelocationRoom:
    return RelocationRoom(
        identifier,
        capabilities,
        "2026-09-02T08:00:00+02:00",
        "2026-09-02T18:00:00+02:00",
    )


def test_relocates_by_priority_and_prevents_double_booking() -> None:
    rows = relocate_room_outages(
        [
            appointment("routine", "2026-09-02T10:00:00+02:00", 2, {"accessible"}),
            appointment("urgent", "2026-09-02T10:00:00+02:00", 5, {"accessible", "ultrasound"}),
        ],
        [room("room-a", {"accessible", "ultrasound"}), room("room-b", {"accessible"})],
    )

    assert [(row.appointment_id, row.replacement_room_id) for row in rows] == [
        ("urgent", "room-a"),
        ("routine", "room-b"),
    ]


def test_honors_existing_bookings_and_reports_unplaced_appointments() -> None:
    rows = relocate_room_outages(
        [appointment("visit", "2026-09-02T10:00:00+02:00", 3, {"accessible"})],
        [room("room-a", {"accessible"})],
        [RoomBooking("existing", "room-a", "2026-09-02T09:45:00+02:00", "2026-09-02T10:15:00+02:00")],
    )

    assert rows == [RoomRelocation("visit", None, False, "no capable conflict-free room")]


def test_rejects_duplicate_and_unknown_booking_inputs() -> None:
    visit = appointment("visit", "2026-09-02T10:00:00+02:00", 3, set())
    candidate = room("room-a", set())
    with pytest.raises(DomainError, match="duplicate outage appointment"):
        relocate_room_outages([visit, visit], [candidate])
    with pytest.raises(DomainError, match="unknown relocation room"):
        relocate_room_outages(
            [],
            [candidate],
            [RoomBooking("booking", "missing", "2026-09-02T10:00:00+02:00", "2026-09-02T11:00:00+02:00")],
        )


def test_rejects_invalid_priority_and_room_windows() -> None:
    invalid = appointment("visit", "2026-09-02T10:00:00+02:00", 0, set())
    with pytest.raises(DomainError, match="priority"):
        relocate_room_outages([invalid], [room("room-a", set())])
    with pytest.raises(DomainError, match="positive duration"):
        relocate_room_outages(
            [],
            [RelocationRoom("room-a", set(), "2026-09-02T11:00:00+02:00", "2026-09-02T10:00:00+02:00")],
        )
