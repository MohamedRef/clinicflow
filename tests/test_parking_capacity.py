import pytest

from clinicflow import (
    ClinicParkingCapacity,
    DomainError,
    ParkingArrival,
    allocate_clinic_parking,
)


def test_parking_allocation_protects_accessible_capacity() -> None:
    arrivals = [
        ParkingArrival("accessible", "clinic", 10, 40, True),
        ParkingArrival("standard-a", "clinic", 10, 30),
        ParkingArrival("standard-b", "clinic", 20, 50),
    ]
    got = allocate_clinic_parking(arrivals, [ClinicParkingCapacity("clinic", 1, 1)])
    by_id = {item.appointment_id: item for item in got}
    assert by_id["accessible"].space_type == "accessible"
    assert by_id["standard-a"].allocated
    assert not by_id["standard-b"].allocated


def test_parking_space_is_reused_after_departure() -> None:
    arrivals = [ParkingArrival("first", "c", 10, 20), ParkingArrival("second", "c", 20, 30)]
    assert all(item.allocated for item in allocate_clinic_parking(arrivals, [ClinicParkingCapacity("c", 1, 0)]))


def test_parking_rejects_duplicate_appointments() -> None:
    arrival = ParkingArrival("same", "c", 10, 20)
    with pytest.raises(DomainError, match="duplicate"):
        allocate_clinic_parking([arrival, arrival], [ClinicParkingCapacity("c", 1, 0)])
