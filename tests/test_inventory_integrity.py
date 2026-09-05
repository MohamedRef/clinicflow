from typing import Any

import pytest

from clinicflow import ClinicFlow, DomainError


@pytest.mark.parametrize("quantity", [True, False, 1.5, "1", None])
def test_inventory_never_interprets_flags_as_quantities(quantity: Any) -> None:
    clinic = ClinicFlow()
    with pytest.raises(DomainError):
        clinic.add_inventory("box", "Supply boxes", quantity, 0)
    with pytest.raises(DomainError):
        clinic.add_inventory("box", "Supply boxes", 4, quantity)
    clinic.add_inventory("box", "Supply boxes", 4, 0)
    before = clinic.to_dict()
    with pytest.raises(DomainError):
        clinic.receive_inventory("box", quantity)
    assert clinic.to_dict() == before
    clinic.add_room("room", "Room", set())
    clinic.add_staff("staff", "Staff", set())
    before = clinic.to_dict()
    with pytest.raises(DomainError):
        clinic.schedule(
            "visit",
            "reference",
            "Room booking",
            "room",
            ["staff"],
            "2026-09-05T09:00:00Z",
            "2026-09-05T10:00:00Z",
            inventory_requirements={"box": quantity},
        )
    assert clinic.to_dict() == before


def test_inventory_receipt_accepts_whole_units() -> None:
    clinic = ClinicFlow()
    clinic.add_inventory("box", "Supply boxes", 0, 0)
    assert clinic.receive_inventory("box", 3).on_hand == 3
