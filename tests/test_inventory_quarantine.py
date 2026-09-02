import pytest

from clinicflow import (
    DomainError,
    InventoryReleaseCheck,
    QuarantinedInventoryLot,
    assess_inventory_quarantine,
)


def test_inventory_quarantine_reports_missing_and_failed_checks() -> None:
    lots = [QuarantinedInventoryLot("lot", 10, ("seal", "count", "label"))]
    checks = [
        InventoryReleaseCheck("lot", "seal", 11, True),
        InventoryReleaseCheck("lot", "count", 12, False),
    ]
    [finding] = assess_inventory_quarantine(lots, checks, 15)
    assert finding.missing_check_ids == ("label",)
    assert finding.failed_check_ids == ("count",)
    assert not finding.releasable


def test_inventory_quarantine_releases_complete_lots() -> None:
    lot = QuarantinedInventoryLot("lot", 10, ("seal",))
    [finding] = assess_inventory_quarantine([lot], [InventoryReleaseCheck("lot", "seal", 10, True)], 10)
    assert finding.releasable


def test_inventory_quarantine_rejects_undeclared_checks() -> None:
    with pytest.raises(DomainError, match="declared"):
        assess_inventory_quarantine(
            [QuarantinedInventoryLot("lot", 10, ("seal",))],
            [InventoryReleaseCheck("lot", "label", 11, True)],
            12,
        )
