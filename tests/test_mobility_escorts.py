import pytest

from clinicflow import (
    DomainError,
    MobilityEscortRequest,
    MobilityEscortShift,
    allocate_mobility_escorts,
)


def test_mobility_escort_allocation_protects_trained_capacity() -> None:
    shifts = [
        MobilityEscortShift("trained", "clinic", 0, 100, True),
        MobilityEscortShift("general", "clinic", 0, 100, False),
    ]
    requests = [
        MobilityEscortRequest("accessible", "clinic", 10, 30, True),
        MobilityEscortRequest("general", "clinic", 10, 30),
    ]
    got = {item.appointment_id: item for item in allocate_mobility_escorts(requests, shifts)}
    assert got["accessible"].escort_id == "trained"
    assert got["general"].escort_id == "general"


def test_mobility_escort_capacity_blocks_overlapping_requests() -> None:
    shift = MobilityEscortShift("escort", "clinic", 0, 100, True)
    requests = [
        MobilityEscortRequest("first", "clinic", 10, 40),
        MobilityEscortRequest("second", "clinic", 20, 30),
    ]
    got = allocate_mobility_escorts(requests, [shift])
    assert got[0].assigned
    assert not got[1].assigned


def test_mobility_escort_allocation_rejects_duplicate_requests() -> None:
    request = MobilityEscortRequest("same", "clinic", 10, 20)
    with pytest.raises(DomainError, match="duplicate"):
        allocate_mobility_escorts([request, request], [])
