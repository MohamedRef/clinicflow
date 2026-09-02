import pytest

from clinicflow import DomainError, PrivacyScreen, PrivacyScreenDemand, allocate_privacy_screens


def test_privacy_screen_allocation_prioritizes_overlapping_demand() -> None:
    screen = PrivacyScreen("screen", "clinic", 9, False)
    demands = [
        PrivacyScreenDemand("routine", "clinic", 10, 30, 1),
        PrivacyScreenDemand("urgent", "clinic", 20, 40, 5),
    ]
    got = allocate_privacy_screens([screen], demands, 10, 5)
    assert got[0].room_id == "urgent" and got[0].assigned
    assert not got[1].assigned


def test_privacy_screen_allocation_ignores_damaged_screens() -> None:
    got = allocate_privacy_screens(
        [PrivacyScreen("screen", "clinic", 9, True)],
        [PrivacyScreenDemand("room", "clinic", 10, 30, 1)],
        10,
        5,
    )
    assert got[0].reason == "no_available_screen"


def test_privacy_screen_allocation_rejects_duplicate_rooms() -> None:
    demand = PrivacyScreenDemand("room", "clinic", 10, 30, 1)
    with pytest.raises(DomainError, match="duplicate"):
        allocate_privacy_screens([], [demand, demand], 10, 5)
