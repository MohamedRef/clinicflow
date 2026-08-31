import pytest

from clinicflow import DomainError, ReceptionArrival, ReceptionDeskCapacity, assess_reception_capacity


def test_reception_capacity_treats_adjacent_arrivals_as_non_overlapping() -> None:
    got = assess_reception_capacity(
        [
            ReceptionArrival("a", "clinic", "2026-08-31T09:00:00Z", 30),
            ReceptionArrival("b", "clinic", "2026-08-31T09:15:00Z", 30),
            ReceptionArrival("c", "clinic", "2026-08-31T09:30:00Z", 30),
        ],
        [ReceptionDeskCapacity("clinic", 1)],
    )
    assert len(got) == 1
    assert got[0].peak_arrivals == 2
    assert got[0].shortfall == 1


def test_reception_capacity_requires_configured_clinic() -> None:
    with pytest.raises(DomainError, match="capacity missing"):
        assess_reception_capacity([ReceptionArrival("a", "clinic", "2026-08-31T09:00:00Z", 10)], [])
