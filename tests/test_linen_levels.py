import pytest

from clinicflow import DomainError, RoomLinenPosition, plan_linen_replenishment


def test_linen_replenishment_accounts_for_reserved_stock() -> None:
    got = plan_linen_replenishment(
        [
            RoomLinenPosition("room-a", "sheet", 10, 4, 8),
            RoomLinenPosition("room-b", "sheet", 12, 2, 8),
            RoomLinenPosition("room-c", "gown", 3, 0, 8),
        ]
    )
    assert [(item.room_id, item.replenish_quantity) for item in got] == [("room-c", 5), ("room-a", 2)]


def test_linen_replenishment_rejects_over_reservation() -> None:
    with pytest.raises(DomainError, match="cannot exceed"):
        plan_linen_replenishment([RoomLinenPosition("room", "sheet", 1, 2, 3)])
