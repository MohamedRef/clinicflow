from dataclasses import replace

import pytest

from clinicflow import DomainError, RoomStock, TransferRequest, plan_inventory_transfers


def stock(lot_id: str, room_id: str, quantity: int, reserved: int = 0) -> RoomStock:
    return RoomStock(
        lot_id,
        room_id,
        "kit-a",
        quantity,
        reserved,
        "2026-09-03T08:00:00+02:00",
        "2026-09-04T08:00:00+02:00",
    )


def request(identifier: str, quantity: int) -> TransferRequest:
    return TransferRequest(identifier, "room-c", "kit-a", quantity, "2026-09-03T12:00:00+02:00")


def test_allocates_earliest_expiring_unreserved_stock() -> None:
    later = replace(stock("lot-later", "room-a", 8), expires_at="2026-09-05T08:00:00+02:00")
    earlier = stock("lot-earlier", "room-b", 10, reserved=4)
    transfers, shortages = plan_inventory_transfers([request("req-1", 9)], [later, earlier])
    assert [(row.lot_id, row.quantity) for row in transfers] == [("lot-earlier", 6), ("lot-later", 3)]
    assert shortages == []


def test_excludes_destination_stock_and_reports_shortage() -> None:
    transfers, shortages = plan_inventory_transfers(
        [request("req-2", 7)],
        [stock("local", "room-c", 10), stock("remote", "room-b", 3)],
    )
    assert [(row.lot_id, row.quantity) for row in transfers] == [("remote", 3)]
    assert shortages[0].missing_quantity == 4


def test_rejects_casefold_duplicates_and_over_reserved_stock() -> None:
    with pytest.raises(DomainError, match="duplicate transfer lot"):
        plan_inventory_transfers([], [stock("Lot-A", "room-a", 2), stock("lot-a", "room-b", 2)])
    with pytest.raises(DomainError, match="cannot exceed"):
        plan_inventory_transfers([], [stock("lot-a", "room-a", 2, reserved=3)])
    with pytest.raises(DomainError, match="duplicate transfer request"):
        plan_inventory_transfers(
            [request("Req-A", 1), request("req-a", 1)],
            [stock("lot-a", "room-a", 2)],
        )
