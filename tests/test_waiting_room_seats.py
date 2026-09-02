import pytest

from clinicflow import DomainError, WaitingParty, WaitingRoomZone, allocate_waiting_room_seats


def test_waiting_room_seats_prioritize_accessible_party() -> None:
    zones = [WaitingRoomZone("zone", "clinic", 2, 1, True)]
    parties = [
        WaitingParty("routine", "clinic", 2, 0, 1),
        WaitingParty("priority", "clinic", 2, 1, 5),
    ]
    got = allocate_waiting_room_seats(zones, parties)
    assert got[0].party_id == "priority" and got[0].assigned
    assert not got[1].assigned


def test_waiting_room_seats_exclude_closed_zones() -> None:
    got = allocate_waiting_room_seats(
        [WaitingRoomZone("zone", "clinic", 2, 1, False)],
        [WaitingParty("party", "clinic", 1, 0, 1)],
    )
    assert got[0].reason == "no_capacity"


def test_waiting_room_seats_reject_duplicate_parties() -> None:
    party = WaitingParty("party", "clinic", 1, 0, 1)
    with pytest.raises(DomainError, match="duplicated"):
        allocate_waiting_room_seats([], [party, party])
