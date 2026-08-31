import pytest

from clinicflow import RoomUtilityCheck, RoomUtilityFinding, assess_room_utilities
from clinicflow.models import DomainError


def test_prioritizes_unavailable_room_utilities() -> None:
    result = assess_room_utilities(
        [
            RoomUtilityCheck("room-1", "power", True, False, False),
            RoomUtilityCheck("room-2", "network", True, False, True),
            RoomUtilityCheck("room-3", "power", True, True, False),
            RoomUtilityCheck("room-4", "network", False, False, False),
        ]
    )
    assert result == [
        RoomUtilityFinding("room-1", "power", "unavailable"),
        RoomUtilityFinding("room-2", "network", "backup_only"),
    ]


def test_rejects_duplicate_room_utility_checks() -> None:
    row = RoomUtilityCheck("room", "power", True, True, False)
    with pytest.raises(DomainError, match="duplicate"):
        assess_room_utilities([row, row])
