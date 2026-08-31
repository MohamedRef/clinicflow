from datetime import UTC, datetime, timedelta

from clinicflow import (
    ScheduledSupplyDelivery,
    SupplyDeliveryReceipt,
    SupplyReceivingFinding,
    reconcile_supply_receiving,
)


def test_reconciles_supply_receiving_exceptions() -> None:
    start = datetime(2026, 9, 1, 9, tzinfo=UTC)
    deliveries = [
        ScheduledSupplyDelivery("damaged", "supplier", 4, start, start + timedelta(hours=1)),
        ScheduledSupplyDelivery("short", "supplier", 4, start, start + timedelta(hours=1)),
        ScheduledSupplyDelivery("missing", "supplier", 4, start, start + timedelta(hours=1)),
    ]
    receipts = [
        SupplyDeliveryReceipt("damaged", 4, start, False),
        SupplyDeliveryReceipt("short", 3, start, True),
    ]
    result = reconcile_supply_receiving(deliveries, receipts, start + timedelta(hours=2))
    assert result == [
        SupplyReceivingFinding("damaged", "supplier", "seal_damaged", 0),
        SupplyReceivingFinding("missing", "supplier", "missing_receipt", -4),
        SupplyReceivingFinding("short", "supplier", "quantity_mismatch", -1),
    ]


def test_does_not_mark_future_delivery_missing() -> None:
    start = datetime(2026, 9, 1, 9, tzinfo=UTC)
    delivery = ScheduledSupplyDelivery("delivery", "supplier", 1, start, start + timedelta(hours=1))
    assert reconcile_supply_receiving([delivery], [], start) == []
