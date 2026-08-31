import pytest

from clinicflow import (
    CleaningSupplyBatch,
    CleaningSupplyDemand,
    DomainError,
    allocate_cleaning_supplies,
)


def test_cleaning_supply_allocation_uses_earliest_unexpired_stock() -> None:
    allocations, shortages = allocate_cleaning_supplies(
        [
            CleaningSupplyBatch("expired", "disinfectant", 4, "2026-08-31"),
            CleaningSupplyBatch("early", "disinfectant", 3, "2026-09-02"),
            CleaningSupplyBatch("later", "disinfectant", 4, "2026-09-10"),
        ],
        [CleaningSupplyDemand("turnover", "disinfectant", 5, "2026-09-01")],
    )
    assert [(item.batch_id, item.units) for item in allocations] == [("early", 3), ("later", 2)]
    assert shortages == []


def test_cleaning_supply_allocation_reports_shortage() -> None:
    _, shortages = allocate_cleaning_supplies(
        [CleaningSupplyBatch("b", "wipe", 1, "2026-09-10")],
        [CleaningSupplyDemand("t", "wipe", 3, "2026-09-01")],
    )
    assert shortages[0].missing_units == 2


def test_cleaning_supply_allocation_rejects_duplicate_batches() -> None:
    batch = CleaningSupplyBatch("b", "wipe", 1, "2026-09-10")
    with pytest.raises(DomainError, match="duplicate"):
        allocate_cleaning_supplies([batch, batch], [])
