import pytest

from clinicflow import InventoryCycleCount, InventoryLedgerPosition, reconcile_cycle_counts
from clinicflow.models import DomainError


def test_reports_material_and_unwitnessed_controlled_variance() -> None:
    rows = reconcile_cycle_counts(
        [InventoryLedgerPosition("item", "store", 10, 500, True)],
        [InventoryCycleCount("item", "store", 7, False)],
        material_variance_cents=1_000,
    )
    assert rows[0].variance_value_cents == -1_500
    assert rows[0].blockers == ("witness_missing", "material_variance")


def test_rejects_unknown_cycle_count() -> None:
    with pytest.raises(DomainError, match="invalid"):
        reconcile_cycle_counts([], [InventoryCycleCount("item", "store", 1, True)], material_variance_cents=0)
