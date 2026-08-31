import pytest

from clinicflow import (
    DomainError,
    SealedWasteBag,
    WasteCollectionReceipt,
    WasteHandoffStatus,
    reconcile_waste_handoffs,
)


def test_waste_handoffs_distinguish_missing_late_and_matched_receipts() -> None:
    bags = [
        SealedWasteBag("missing", "clinic", "general", "2026-08-31T08:00:00Z", "2026-08-31T10:00:00Z"),
        SealedWasteBag("late", "clinic", "sharps", "2026-08-31T08:00:00Z", "2026-08-31T10:00:00Z"),
        SealedWasteBag("matched", "clinic", "general", "2026-08-31T08:00:00Z", "2026-08-31T10:00:00Z"),
    ]
    receipts = [
        WasteCollectionReceipt("late", "vendor", "manifest-1", "2026-08-31T11:00:00Z"),
        WasteCollectionReceipt("matched", "vendor", "manifest-2", "2026-08-31T09:00:00Z"),
    ]
    got = reconcile_waste_handoffs(bags, receipts)
    assert [(item.bag_id, item.status) for item in got] == [
        ("missing", WasteHandoffStatus.MISSING),
        ("late", WasteHandoffStatus.LATE),
        ("matched", WasteHandoffStatus.MATCHED),
    ]


def test_waste_handoffs_reject_unknown_bag_receipts() -> None:
    with pytest.raises(DomainError, match="bag missing"):
        reconcile_waste_handoffs([], [WasteCollectionReceipt("unknown", "vendor", "manifest", "2026-08-31T09:00:00Z")])
