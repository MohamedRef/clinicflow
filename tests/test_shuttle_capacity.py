import pytest

from clinicflow import DomainError, ShuttleArrival, ShuttleBay, schedule_shuttle_arrivals


def test_shuttle_schedule_prioritizes_overlapping_arrivals() -> None:
    bay = ShuttleBay("bay", "clinic", 8, 0, 100)
    arrivals = [
        ShuttleArrival("routine", "clinic", 20, 20, 4, 1),
        ShuttleArrival("priority", "clinic", 20, 20, 4, 5),
    ]
    got = schedule_shuttle_arrivals(arrivals, [bay])
    assert got[0].trip_id == "priority" and got[0].assigned
    assert not got[1].assigned


def test_shuttle_schedule_enforces_passenger_limit() -> None:
    got = schedule_shuttle_arrivals(
        [ShuttleArrival("trip", "clinic", 20, 10, 9, 1)],
        [ShuttleBay("bay", "clinic", 8, 0, 100)],
    )
    assert got[0].reason == "no_compatible_bay"


def test_shuttle_schedule_rejects_duplicate_trips() -> None:
    trip = ShuttleArrival("trip", "clinic", 20, 10, 2, 1)
    with pytest.raises(DomainError, match="duplicate"):
        schedule_shuttle_arrivals([trip, trip], [])
