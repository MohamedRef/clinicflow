import pytest

from clinicflow import DeliveryDockWindow, DomainError, SupplyDeliveryRequest, schedule_delivery_docks


def test_delivery_docks_protect_priority_and_cold_chain() -> None:
    windows = [DeliveryDockWindow("cold", "2026-09-04T08:00:00Z", "2026-09-04T10:00:00Z", 10, True)]
    rows = schedule_delivery_docks(
        windows,
        [
            SupplyDeliveryRequest("routine", "2026-09-04T08:00:00Z", 5, 90, False, 1),
            SupplyDeliveryRequest("urgent", "2026-09-04T08:00:00Z", 5, 60, True, 5),
        ],
    )
    assert rows[0].delivery_id == "urgent" and rows[0].assigned
    assert rows[1].assigned is False


def test_delivery_docks_reject_case_aliased_docks() -> None:
    rows = [
        DeliveryDockWindow("Dock", "2026-09-04T08:00:00Z", "2026-09-04T10:00:00Z", 10, False),
        DeliveryDockWindow("dock", "2026-09-04T08:00:00Z", "2026-09-04T10:00:00Z", 10, False),
    ]
    with pytest.raises(DomainError, match="duplicate"):
        schedule_delivery_docks(rows, [])
