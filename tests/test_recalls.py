"""Public behavior tests for recalled clinic supply allocation."""

import pytest

from clinicflow import InventoryBatch, ScheduledBatchAllocation, replace_recalled_allocations
from clinicflow.models import DomainError


def allocation(identifier: str, priority: int, quantity: int) -> ScheduledBatchAllocation:
    return ScheduledBatchAllocation(
        identifier,
        "kit",
        "recalled",
        quantity,
        "2026-09-01T09:00:00+00:00",
        priority,
    )


def test_replaces_recalled_lots_by_priority_and_expiry() -> None:
    replacements, shortages = replace_recalled_allocations(
        [allocation("routine", 1, 4), allocation("urgent", 5, 5)],
        {"recalled"},
        [
            InventoryBatch("late", "kit", 10, "2026-10-01T00:00:00+00:00"),
            InventoryBatch("early", "kit", 3, "2026-09-02T00:00:00+00:00"),
        ],
    )
    assert [(row.appointment_id, row.replacement_lot_id, row.quantity) for row in replacements] == [
        ("urgent", "early", 3),
        ("urgent", "late", 2),
        ("routine", "late", 4),
    ]
    assert shortages == []


def test_reports_exact_recall_replacement_shortage() -> None:
    replacements, shortages = replace_recalled_allocations(
        [allocation("appointment", 3, 5)],
        {"recalled"},
        [InventoryBatch("replacement", "kit", 2, "2026-09-02T00:00:00+00:00")],
    )
    assert replacements[0].quantity == 2
    assert shortages[0].missing_quantity == 3


def test_rejects_recalled_replacement_and_duplicate_allocations() -> None:
    row = allocation("appointment", 3, 1)
    with pytest.raises(DomainError, match="recalled lot cannot"):
        replace_recalled_allocations(
            [row], {"recalled"}, [InventoryBatch("recalled", "kit", 2, "2026-09-02T00:00:00+00:00")]
        )
    with pytest.raises(DomainError, match="duplicate scheduled"):
        replace_recalled_allocations([row, row], {"recalled"}, [])
