import pytest

from clinicflow import (
    DocumentScanBatch,
    DomainError,
    ScannerShift,
    schedule_document_scanning,
)


def test_document_scanning_uses_fastest_available_finish() -> None:
    shifts = [
        ScannerShift("slow", "clinic", 0, 100, 2),
        ScannerShift("fast", "clinic", 0, 100, 5),
    ]
    got = schedule_document_scanning(
        [DocumentScanBatch("batch", "clinic", 20, 10, 20)],
        shifts,
    )
    assert got[0].scanner_id == "fast"
    assert got[0].start_minute == 10
    assert got[0].finish_minute == 14
    assert got[0].on_time


def test_document_scanning_reports_unplaceable_batches() -> None:
    got = schedule_document_scanning(
        [DocumentScanBatch("batch", "clinic", 100, 0, 10)],
        [ScannerShift("scanner", "clinic", 0, 5, 1)],
    )
    assert got[0].scanner_id is None
    assert not got[0].on_time


def test_document_scanning_rejects_duplicate_batches() -> None:
    batch = DocumentScanBatch("same", "clinic", 1, 0, 1)
    with pytest.raises(DomainError, match="duplicate"):
        schedule_document_scanning([batch, batch], [])
