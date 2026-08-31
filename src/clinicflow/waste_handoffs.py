"""Reconcile sealed clinic waste bags with accountable collection handoffs."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .models import DomainError, clean_code, parse_time


class WasteHandoffStatus(StrEnum):
    MATCHED = "matched"
    MISSING = "missing"
    LATE = "late"


@dataclass(frozen=True, slots=True)
class SealedWasteBag:
    bag_id: str
    clinic_id: str
    waste_stream: str
    sealed_at: str
    collection_due_at: str


@dataclass(frozen=True, slots=True)
class WasteCollectionReceipt:
    bag_id: str
    collector: str
    manifest_reference: str
    collected_at: str


@dataclass(frozen=True, slots=True)
class WasteHandoffFinding:
    bag_id: str
    clinic_id: str
    waste_stream: str
    status: WasteHandoffStatus
    collected_at: datetime | None


def reconcile_waste_handoffs(
    bags: list[SealedWasteBag], receipts: list[WasteCollectionReceipt]
) -> list[WasteHandoffFinding]:
    """Match collection receipts and flag missing or late waste custody transfers."""
    expected: dict[str, tuple[SealedWasteBag, datetime, datetime]] = {}
    for bag in bags:
        bag_id = clean_code(bag.bag_id, "waste bag id")
        clinic_id = clean_code(bag.clinic_id, "waste bag clinic")
        stream = clean_code(bag.waste_stream, "waste stream")
        if bag_id in expected:
            raise DomainError(f"duplicate sealed waste bag: {bag_id}")
        sealed_at = parse_time(bag.sealed_at, "waste sealed_at")
        due_at = parse_time(bag.collection_due_at, "waste collection_due_at")
        if due_at <= sealed_at:
            raise DomainError("waste collection deadline must follow sealing")
        expected[bag_id] = (
            SealedWasteBag(bag_id, clinic_id, stream, bag.sealed_at, bag.collection_due_at),
            sealed_at,
            due_at,
        )
    collected: dict[str, datetime] = {}
    for receipt in receipts:
        bag_id = clean_code(receipt.bag_id, "waste receipt bag id")
        clean_code(receipt.collector, "waste collector")
        clean_code(receipt.manifest_reference, "waste manifest reference")
        if bag_id not in expected:
            raise DomainError(f"sealed waste bag missing for receipt: {bag_id}")
        if bag_id in collected:
            raise DomainError(f"duplicate waste collection receipt: {bag_id}")
        collected_at = parse_time(receipt.collected_at, "waste collected_at")
        if collected_at < expected[bag_id][1]:
            raise DomainError("waste collection cannot predate sealing")
        collected[bag_id] = collected_at
    findings: list[WasteHandoffFinding] = []
    for bag_id, (bag, _, due_at) in expected.items():
        receipt_time = collected.get(bag_id)
        status = WasteHandoffStatus.MISSING
        if receipt_time is not None:
            status = WasteHandoffStatus.LATE if receipt_time > due_at else WasteHandoffStatus.MATCHED
        findings.append(WasteHandoffFinding(bag_id, bag.clinic_id, bag.waste_stream, status, receipt_time))
    rank = {WasteHandoffStatus.MISSING: 0, WasteHandoffStatus.LATE: 1, WasteHandoffStatus.MATCHED: 2}
    return sorted(findings, key=lambda item: (rank[item.status], item.bag_id))
