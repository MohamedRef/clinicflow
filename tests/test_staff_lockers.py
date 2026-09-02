import pytest

from clinicflow import DomainError, StaffLocker, StaffLockerRequest, allocate_staff_lockers


def test_staff_lockers_prioritize_accessible_requests() -> None:
    lockers = [StaffLocker("locker", "clinic", True, True)]
    requests = [
        StaffLockerRequest("routine", "clinic", 10, 30, False, 1),
        StaffLockerRequest("priority", "clinic", 10, 30, True, 5),
    ]
    got = allocate_staff_lockers(lockers, requests)
    assert got[0].staff_id == "priority" and got[0].assigned
    assert not got[1].assigned


def test_staff_lockers_ignore_unverified_keys() -> None:
    got = allocate_staff_lockers(
        [StaffLocker("locker", "clinic", False, False)],
        [StaffLockerRequest("staff", "clinic", 10, 30, False, 1)],
    )
    assert not got[0].assigned


def test_staff_lockers_reject_duplicate_staff() -> None:
    request = StaffLockerRequest("staff", "clinic", 10, 30, False, 1)
    with pytest.raises(DomainError, match="duplicate"):
        allocate_staff_lockers([], [request, request])
