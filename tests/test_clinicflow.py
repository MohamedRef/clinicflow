from pathlib import Path

import pytest

from clinicflow import (
    AppointmentStatus,
    ClinicFlow,
    ClinicFlowRepository,
    DomainError,
    PersistenceError,
)

START = "2026-08-24T09:00:00+03:00"
END = "2026-08-24T10:00:00+03:00"


def prepared() -> ClinicFlow:
    clinic = ClinicFlow()
    clinic.add_room("room-a", "Procedure Room A", {"accessible", "ultrasound"})
    clinic.add_room("room-b", "Consultation Room", {"accessible"})
    clinic.add_staff("nora", "Nora Said", {"triage", "ultrasound"})
    clinic.add_staff("omar", "Omar Adel", {"assistant"})
    clinic.add_inventory("gel", "Ultrasound gel", 10, 2)
    clinic.add_inventory("drape", "Disposable drape", 4, 1)
    return clinic


def schedule(clinic: ClinicFlow, appointment_id: str = "visit-1"):
    return clinic.schedule(
        appointment_id,
        "patient-804",
        "Imaging preparation",
        "room-a",
        ["nora", "omar"],
        START,
        END,
        required_room_capabilities={"ultrasound"},
        required_qualifications={"ultrasound", "assistant"},
        inventory_requirements={"gel": 2, "drape": 1},
    )


def test_scheduling_reserves_inventory_and_reports_readiness() -> None:
    clinic = prepared()
    item = schedule(clinic)
    assert item.status is AppointmentStatus.SCHEDULED
    assert item.staff_ids == ["nora", "omar"]
    assert clinic.inventory_report()[1]["reserved"] == 2
    assert clinic.readiness(item.id) == {
        "appointment_id": "visit-1",
        "status": "scheduled",
        "room_active": True,
        "staff_active": True,
        "inventory_shortages": {},
        "ready": True,
    }


def test_room_capabilities_and_staff_qualifications_are_required() -> None:
    clinic = prepared()
    with pytest.raises(DomainError, match="room lacks capabilities"):
        clinic.schedule(
            "bad-room", "p", "procedure", "room-b", ["nora"], START, END, required_room_capabilities={"ultrasound"}
        )
    with pytest.raises(DomainError, match="staff lack qualifications"):
        clinic.schedule(
            "bad-staff", "p", "procedure", "room-a", ["omar"], START, END, required_qualifications={"triage"}
        )


def test_overlap_rules_cover_rooms_staff_and_maintenance() -> None:
    clinic = prepared()
    schedule(clinic)
    with pytest.raises(DomainError, match="room is unavailable"):
        clinic.schedule(
            "visit-2", "p2", "follow-up", "room-a", ["omar"], "2026-08-24T09:30:00+03:00", "2026-08-24T10:30:00+03:00"
        )
    with pytest.raises(DomainError, match="staff member is unavailable"):
        clinic.schedule(
            "visit-3", "p3", "follow-up", "room-b", ["nora"], "2026-08-24T09:30:00+03:00", "2026-08-24T10:30:00+03:00"
        )
    with pytest.raises(DomainError, match="overlaps a scheduled appointment"):
        clinic.block_room(
            "repair", "room-a", "2026-08-24T09:45:00+03:00", "2026-08-24T11:00:00+03:00", "Probe calibration"
        )


def test_maintenance_blocks_future_scheduling_but_allows_boundaries() -> None:
    clinic = prepared()
    clinic.block_room("repair", "room-a", END, "2026-08-24T11:00:00+03:00", "Electrical inspection")
    schedule(clinic)
    with pytest.raises(DomainError, match="room is unavailable"):
        clinic.schedule("visit-2", "p2", "procedure", "room-a", ["nora"], END, "2026-08-24T10:30:00+03:00")


def test_cancel_releases_reservations_and_enforces_version() -> None:
    clinic = prepared()
    item = schedule(clinic)
    with pytest.raises(DomainError, match="version conflict"):
        clinic.cancel(item.id, "patient request", 99)
    cancelled = clinic.cancel(item.id, " Patient   request ", item.version)
    assert cancelled.status is AppointmentStatus.CANCELLED
    assert cancelled.cancellation_reason == "Patient request"
    assert all(row["reserved"] == 0 for row in clinic.inventory_report())
    with pytest.raises(DomainError, match="only scheduled"):
        clinic.complete(item.id, cancelled.version)


def test_complete_consumes_reserved_inventory() -> None:
    clinic = prepared()
    item = schedule(clinic)
    completed = clinic.complete(item.id, item.version)
    assert completed.status is AppointmentStatus.COMPLETED
    report = {row["sku"]: row for row in clinic.inventory_report()}
    assert report["gel"]["on_hand"] == 8
    assert report["gel"]["reserved"] == 0
    assert report["drape"]["on_hand"] == 3


def test_inventory_shortage_and_receiving_workflow() -> None:
    clinic = prepared()
    with pytest.raises(DomainError, match="insufficient available inventory"):
        clinic.schedule("large", "p", "procedure", "room-a", ["nora"], START, END, inventory_requirements={"drape": 5})
    updated = clinic.receive_inventory("drape", 2)
    assert updated.on_hand == 6
    item = clinic.schedule(
        "large", "p", "procedure", "room-a", ["nora"], START, END, inventory_requirements={"drape": 5}
    )
    assert item.inventory_requirements == {"drape": 5}
    assert {row["sku"]: row for row in clinic.inventory_report()}["drape"]["below_reorder"]


def test_deactivation_protects_scheduled_work() -> None:
    clinic = prepared()
    item = schedule(clinic)
    with pytest.raises(DomainError, match="scheduled appointments"):
        clinic.deactivate_room("room-a")
    with pytest.raises(DomainError, match="scheduled appointments"):
        clinic.deactivate_staff("nora")
    clinic.cancel(item.id, "rescheduled", item.version)
    assert not clinic.deactivate_room("room-a").active
    assert not clinic.deactivate_staff("nora").active


def test_lists_are_deterministic_and_results_are_defensive_copies() -> None:
    clinic = prepared()
    later = clinic.schedule(
        "later", "p2", "follow-up", "room-b", ["omar"], "2026-08-24T12:00:00+03:00", "2026-08-24T13:00:00+03:00"
    )
    earlier = schedule(clinic, "earlier")
    rows = clinic.appointments()
    assert [row.id for row in rows] == [earlier.id, later.id]
    rows[0].staff_ids.clear()
    assert clinic.appointment(earlier.id).staff_ids == ["nora", "omar"]


def test_repository_round_trip_is_atomic_and_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "state" / "clinic.json"
    repository = ClinicFlowRepository(path)
    clinic = prepared()
    item = schedule(clinic)
    repository.save(clinic)
    restored = repository.load()
    assert restored.appointment(item.id) == item
    assert restored.inventory_report() == clinic.inventory_report()
    first = path.read_text(encoding="utf-8")
    repository.save(restored)
    assert path.read_text(encoding="utf-8") == first
    assert not path.with_suffix(".json.tmp").exists()


def test_repository_fails_closed_on_corrupt_or_unknown_snapshots(tmp_path: Path) -> None:
    path = tmp_path / "clinic.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(PersistenceError, match="cannot load"):
        ClinicFlowRepository(path).load()
    path.write_text('{"schema_version": 99}', encoding="utf-8")
    with pytest.raises(PersistenceError, match="unsupported"):
        ClinicFlowRepository(path).load()


def test_empty_repository_loads_a_new_clinic(tmp_path: Path) -> None:
    clinic = ClinicFlowRepository(tmp_path / "missing.json").load()
    assert clinic.appointments() == []
    assert clinic.inventory_report() == []


def test_identifiers_and_duplicate_resources_are_validated() -> None:
    clinic = prepared()
    with pytest.raises(DomainError, match="room already exists"):
        clinic.add_room("room-a", "Duplicate", set())
    with pytest.raises(DomainError, match="staff member already exists"):
        clinic.add_staff("nora", "Duplicate", set())
    with pytest.raises(DomainError, match="inventory item already exists"):
        clinic.add_inventory("gel", "Duplicate", 1, 0)
    with pytest.raises(DomainError, match="may contain only"):
        clinic.add_room("bad room", "Bad", set())
    with pytest.raises(DomainError, match="non-negative"):
        clinic.add_inventory("bad", "Bad", -1, 0)


def test_schedule_validates_people_requirements_and_known_resources() -> None:
    clinic = prepared()
    with pytest.raises(DomainError, match="at least one"):
        clinic.schedule("none", "p", "procedure", "room-a", [], START, END)
    with pytest.raises(DomainError, match="staff ids must be unique"):
        clinic.schedule("dupe", "p", "procedure", "room-a", ["nora", "nora"], START, END)
    with pytest.raises(DomainError, match="positive integers"):
        clinic.schedule(
            "bad-quantity", "p", "procedure", "room-a", ["nora"], START, END, inventory_requirements={"gel": 0}
        )
    with pytest.raises(DomainError, match="inventory item not found"):
        clinic.schedule(
            "missing-stock", "p", "procedure", "room-a", ["nora"], START, END, inventory_requirements={"missing": 1}
        )
    with pytest.raises(DomainError, match="staff member not found"):
        clinic.schedule("missing-staff", "p", "procedure", "room-a", ["missing"], START, END)


def test_inactive_resources_cannot_receive_new_work() -> None:
    clinic = prepared()
    clinic.deactivate_room("room-b")
    with pytest.raises(DomainError, match="room is inactive"):
        clinic.schedule("inactive-room", "p", "procedure", "room-b", ["omar"], START, END)
    clinic.deactivate_staff("omar")
    with pytest.raises(DomainError, match="inactive staff"):
        clinic.schedule("inactive-staff", "p", "procedure", "room-a", ["omar"], START, END)


def test_maintenance_ids_and_windows_are_unique() -> None:
    clinic = prepared()
    clinic.block_room("repair", "room-a", START, END, "Calibration")
    with pytest.raises(DomainError, match="already exists"):
        clinic.block_room("repair", "room-b", START, END, "Different work")
    with pytest.raises(DomainError, match="overlaps an existing block"):
        clinic.block_room("repair-2", "room-a", "2026-08-24T09:30:00+03:00", "2026-08-24T10:30:00+03:00", "Inspection")


def test_missing_resources_and_invalid_receipts_fail_explicitly() -> None:
    clinic = prepared()
    with pytest.raises(DomainError, match="appointment not found"):
        clinic.appointment("missing")
    with pytest.raises(DomainError, match="room not found"):
        clinic.block_room("block", "missing", START, END, "Repair")
    with pytest.raises(DomainError, match="positive integer"):
        clinic.receive_inventory("gel", 0)
    with pytest.raises(DomainError, match="inventory item not found"):
        clinic.receive_inventory("missing", 1)


@pytest.mark.parametrize(
    "starts_at,ends_at",
    [
        ("2026-08-24T09:00:00", END),
        (START, "2026-08-24T08:00:00+03:00"),
        ("bad", END),
    ],
)
def test_time_windows_are_timezone_aware_and_ordered(starts_at: str, ends_at: str) -> None:
    clinic = prepared()
    with pytest.raises(DomainError):
        clinic.schedule("bad-time", "p", "procedure", "room-a", ["nora"], starts_at, ends_at)
