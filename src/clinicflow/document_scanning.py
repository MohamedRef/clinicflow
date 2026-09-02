"""Schedule appointment-document batches onto clinic scanning capacity."""

from dataclasses import dataclass
from math import ceil

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class ScannerShift:
    scanner_id: str
    clinic_id: str
    start_minute: int
    end_minute: int
    pages_per_minute: int


@dataclass(frozen=True, slots=True)
class DocumentScanBatch:
    batch_id: str
    clinic_id: str
    page_count: int
    ready_minute: int
    due_minute: int


@dataclass(frozen=True, slots=True)
class DocumentScanAssignment:
    batch_id: str
    scanner_id: str | None
    start_minute: int | None
    finish_minute: int | None
    on_time: bool


def schedule_document_scanning(
    batches: list[DocumentScanBatch],
    shifts: list[ScannerShift],
) -> list[DocumentScanAssignment]:
    """Assign earliest-due batches to the scanner that can finish them first."""
    normalized_shifts: list[ScannerShift] = []
    scanner_ids: set[str] = set()
    for shift in shifts:
        scanner_id = clean_code(shift.scanner_id, "scanner id")
        clinic_id = clean_code(shift.clinic_id, "scanner clinic id")
        if scanner_id in scanner_ids:
            raise DomainError(f"duplicate scanner shift: {scanner_id}")
        if shift.start_minute < 0 or shift.end_minute <= shift.start_minute or shift.pages_per_minute < 1:
            raise DomainError("scanner shift has invalid timing or throughput")
        scanner_ids.add(scanner_id)
        normalized_shifts.append(
            ScannerShift(
                scanner_id,
                clinic_id,
                shift.start_minute,
                shift.end_minute,
                shift.pages_per_minute,
            )
        )

    normalized_batches: list[DocumentScanBatch] = []
    batch_ids: set[str] = set()
    for batch in batches:
        batch_id = clean_code(batch.batch_id, "document scan batch id")
        clinic_id = clean_code(batch.clinic_id, "document scan clinic id")
        if batch_id in batch_ids:
            raise DomainError(f"duplicate document scan batch: {batch_id}")
        if batch.page_count < 1 or batch.ready_minute < 0 or batch.due_minute < batch.ready_minute:
            raise DomainError("document scan batch has invalid workload or timing")
        batch_ids.add(batch_id)
        normalized_batches.append(
            DocumentScanBatch(
                batch_id,
                clinic_id,
                batch.page_count,
                batch.ready_minute,
                batch.due_minute,
            )
        )

    available_at = {shift.scanner_id: shift.start_minute for shift in normalized_shifts}
    assignments: list[DocumentScanAssignment] = []
    for batch in sorted(normalized_batches, key=lambda item: (item.due_minute, item.batch_id)):
        candidates: list[tuple[int, int, str]] = []
        for shift in normalized_shifts:
            if shift.clinic_id != batch.clinic_id:
                continue
            start = max(batch.ready_minute, available_at[shift.scanner_id])
            finish = start + ceil(batch.page_count / shift.pages_per_minute)
            if finish <= shift.end_minute:
                candidates.append((finish, start, shift.scanner_id))
        if not candidates:
            assignments.append(DocumentScanAssignment(batch.batch_id, None, None, None, False))
            continue
        finish, start, scanner_id = min(candidates)
        available_at[scanner_id] = finish
        assignments.append(
            DocumentScanAssignment(
                batch.batch_id,
                scanner_id,
                start,
                finish,
                finish <= batch.due_minute,
            )
        )
    return assignments
