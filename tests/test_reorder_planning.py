import pytest

from clinicflow import DomainError, InventoryPosition, ScheduledConsumption, SupplierOffer, plan_inventory_reorders


def test_orders_whole_packs_for_demand_and_safety_stock() -> None:
    rows = plan_inventory_reorders(
        [InventoryPosition("gloves", 10, 2, 3)],
        [ScheduledConsumption("visit", "gloves", 9, "2026-09-07T10:00:00Z")],
        [SupplierOffer("gloves", "supplier", "2026-09-06T10:00:00Z", 5, 3)],
        "2026-09-08T00:00:00Z",
    )
    assert rows[0].order_quantity == 5
    assert rows[0].projected_shortage == 0


def test_reports_capacity_and_horizon_shortages() -> None:
    rows = plan_inventory_reorders(
        [InventoryPosition("kits", 0, 0, 10), InventoryPosition("masks", 0, 0, 5)],
        [],
        [
            SupplierOffer("kits", "limited", "2026-09-06T10:00:00Z", 3, 2),
            SupplierOffer("masks", "late", "2026-09-10T10:00:00Z", 5, 2),
        ],
        "2026-09-08T00:00:00Z",
    )
    by_sku = {row.sku: row for row in rows}
    assert by_sku["kits"].projected_shortage == 4
    assert by_sku["masks"].supplier_id is None


def test_rejects_unknown_sku_and_duplicate_consumption() -> None:
    demand = ScheduledConsumption("demand", "missing", 1, "2026-09-07T10:00:00Z")
    with pytest.raises(DomainError, match="unknown sku"):
        plan_inventory_reorders([], [demand], [], "2026-09-08T00:00:00Z")
    position = InventoryPosition("item", 1, 0, 0)
    demand = ScheduledConsumption("demand", "item", 1, "2026-09-07T10:00:00Z")
    with pytest.raises(DomainError, match="duplicate scheduled consumption"):
        plan_inventory_reorders([position], [demand, demand], [], "2026-09-08T00:00:00Z")
