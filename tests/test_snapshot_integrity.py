from copy import deepcopy

import pytest

from clinicflow import ClinicFlow, DomainError


def valid_snapshot() -> dict[str, object]:
    clinic = ClinicFlow()
    clinic.add_room("room", "Room", set())
    clinic.add_staff("staff", "Staff", set())
    clinic.add_inventory("kit", "Kit", 4, 1)
    clinic.schedule(
        "visit",
        "reference",
        "Visit",
        "room",
        ["staff"],
        "2026-09-05T09:00:00Z",
        "2026-09-05T10:00:00Z",
        inventory_requirements={"kit": 1},
    )
    return clinic.to_dict()


@pytest.mark.parametrize(
    ("collection", "field", "value", "message"),
    [
        ("appointments", "room_id", "missing", "missing room"),
        ("appointments", "staff_ids", ["missing"], "missing staff"),
        ("appointments", "inventory_requirements", {"missing": 1}, "missing inventory"),
        ("inventory", "reserved", 5, "reservations exceed stock"),
        ("inventory", "reserved", 0, "reservation total is inconsistent"),
    ],
)
def test_snapshot_rejects_broken_cross_references_and_inventory_totals(
    collection: str, field: str, value: object, message: str
) -> None:
    snapshot = valid_snapshot()
    rows = snapshot[collection]
    assert isinstance(rows, list)
    rows[0][field] = value
    with pytest.raises(DomainError, match=message):
        ClinicFlow.from_dict(snapshot)


def test_snapshot_rejects_overlapping_scheduled_appointments() -> None:
    snapshot = valid_snapshot()
    appointments = snapshot["appointments"]
    inventory = snapshot["inventory"]
    assert isinstance(appointments, list)
    assert isinstance(inventory, list)
    duplicate = deepcopy(appointments[0])
    duplicate["id"] = "other"
    appointments.append(duplicate)
    inventory[0]["reserved"] = 2
    with pytest.raises(DomainError, match="overlapping room appointments"):
        ClinicFlow.from_dict(snapshot)


def test_snapshot_round_trip_keeps_valid_state() -> None:
    snapshot = valid_snapshot()
    assert ClinicFlow.from_dict(snapshot).to_dict() == snapshot
