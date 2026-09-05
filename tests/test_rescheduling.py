import pytest

from clinicflow import ClinicFlow, DomainError


def clinic_with_visit() -> ClinicFlow:
    clinic = ClinicFlow()
    clinic.add_room("room-a", "Procedure room", {"accessible"})
    clinic.add_room("room-b", "Overflow room", {"accessible"})
    clinic.add_staff("nora", "Nora", {"interpreter"})
    clinic.add_staff("omar", "Omar", {"interpreter"})
    clinic.add_inventory("drape", "Disposable drape", 4, 1)
    clinic.schedule(
        "visit",
        "patient-reference",
        "Non-clinical consultation",
        "room-a",
        ["nora"],
        "2026-09-05T09:00:00Z",
        "2026-09-05T10:00:00Z",
        required_room_capabilities={"accessible"},
        required_qualifications={"interpreter"},
        inventory_requirements={"drape": 1},
    )
    return clinic


def test_reschedule_moves_resources_without_changing_inventory_reservations() -> None:
    clinic = clinic_with_visit()
    moved = clinic.reschedule(
        "visit",
        "2026-09-05T11:00:00Z",
        "2026-09-05T12:00:00Z",
        1,
        room_id="room-b",
        staff_ids=["omar"],
    )
    assert (moved.room_id, moved.staff_ids, moved.version) == ("room-b", ["omar"], 2)
    assert clinic.inventory_report()[0]["reserved"] == 1


def test_reschedule_rejects_conflicts_without_partial_mutation() -> None:
    clinic = clinic_with_visit()
    clinic.schedule(
        "occupied",
        "other-reference",
        "Follow-up",
        "room-b",
        ["omar"],
        "2026-09-05T11:00:00Z",
        "2026-09-05T12:00:00Z",
    )
    before = clinic.to_dict()
    with pytest.raises(DomainError, match="room is unavailable"):
        clinic.reschedule(
            "visit",
            "2026-09-05T11:00:00Z",
            "2026-09-05T12:00:00Z",
            1,
            room_id="room-b",
            staff_ids=["nora"],
        )
    assert clinic.to_dict() == before


def test_reschedule_allows_the_appointment_to_keep_its_own_window() -> None:
    clinic = clinic_with_visit()
    unchanged = clinic.reschedule(
        "visit",
        "2026-09-05T09:00:00Z",
        "2026-09-05T10:00:00Z",
        1,
    )
    assert unchanged.version == 2
