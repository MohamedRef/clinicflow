import pytest

from clinicflow import InventoryBatch, SupplyDemand, allocate_inventory
from clinicflow.models import DomainError


def test_allocates_fefo_batches_without_using_expired_stock() -> None:
    allocations, shortages = allocate_inventory(
        [
            SupplyDemand("appt-1", "gloves", 7, "2026-09-01T09:00:00+00:00"),
            SupplyDemand("appt-2", "gloves", 5, "2026-09-01T10:00:00+00:00"),
        ],
        [
            InventoryBatch("late", "gloves", 10, "2026-10-01T00:00:00+00:00"),
            InventoryBatch("early", "gloves", 4, "2026-09-02T00:00:00+00:00"),
            InventoryBatch("expired", "gloves", 50, "2026-09-01T08:00:00+00:00"),
        ],
    )
    assert [(item.appointment_id, item.lot_id, item.quantity) for item in allocations] == [
        ("appt-1", "early", 4),
        ("appt-1", "late", 3),
        ("appt-2", "late", 5),
    ]
    assert shortages == []


def test_reports_exact_shortages_after_partial_allocation() -> None:
    allocations, shortages = allocate_inventory(
        [SupplyDemand("appt", "kit", 5, "2026-09-01T09:00:00+00:00")],
        [InventoryBatch("lot", "kit", 2, "2026-09-02T00:00:00+00:00")],
    )
    assert allocations[0].quantity == 2
    assert shortages[0].missing_quantity == 3


@pytest.mark.parametrize(
    "demands,batches,message",
    [
        (
            [
                SupplyDemand("a", "kit", 1, "2026-09-01T09:00:00+00:00"),
                SupplyDemand("a", "kit", 2, "2026-09-01T10:00:00+00:00"),
            ],
            [],
            "duplicate appointment",
        ),
        ([], [InventoryBatch("lot", "kit", -1, "2026-09-02T00:00:00+00:00")], "batch quantity"),
        (
            [],
            [
                InventoryBatch("lot", "a", 1, "2026-09-02T00:00:00+00:00"),
                InventoryBatch("lot", "b", 1, "2026-09-02T00:00:00+00:00"),
            ],
            "duplicate inventory lot",
        ),
    ],
)
def test_invalid_inventory_inputs_fail_closed(
    demands: list[SupplyDemand], batches: list[InventoryBatch], message: str
) -> None:
    with pytest.raises(DomainError, match=message):
        allocate_inventory(demands, batches)
