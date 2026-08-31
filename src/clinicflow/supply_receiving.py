"""Reconcile scheduled clinic supply deliveries with receiving records."""

from dataclasses import dataclass
from datetime import datetime

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class ScheduledSupplyDelivery:
    delivery_id: str
    supplier_id: str
    expected_packages: int
    window_start: datetime
    window_end: datetime


@dataclass(frozen=True, slots=True)
class SupplyDeliveryReceipt:
    delivery_id: str
    received_packages: int
    received_at: datetime
    seal_intact: bool


@dataclass(frozen=True, slots=True)
class SupplyReceivingFinding:
    delivery_id: str
    supplier_id: str
    kind: str
    package_variance: int


def reconcile_supply_receiving(
    deliveries: list[ScheduledSupplyDelivery], receipts: list[SupplyDeliveryReceipt], as_of: datetime
) -> list[SupplyReceivingFinding]:
    """Return missing, late, damaged, and quantity-mismatched supply deliveries."""
    if not isinstance(as_of, datetime):
        raise DomainError("supply receiving assessment time is required")
    expected: dict[str, ScheduledSupplyDelivery] = {}
    suppliers: dict[str, str] = {}
    for delivery in deliveries:
        delivery_id = clean_code(delivery.delivery_id, "supply delivery id")
        supplier_id = clean_code(delivery.supplier_id, "supply delivery supplier id")
        if delivery_id in expected:
            raise DomainError(f"duplicate scheduled supply delivery: {delivery_id}")
        if delivery.expected_packages < 1 or delivery.window_end <= delivery.window_start:
            raise DomainError("supply delivery package count and receiving window are invalid")
        expected[delivery_id] = delivery
        suppliers[delivery_id] = supplier_id
    seen: set[str] = set()
    findings: list[SupplyReceivingFinding] = []
    for receipt in receipts:
        delivery_id = clean_code(receipt.delivery_id, "supply receipt delivery id")
        if delivery_id in seen:
            raise DomainError(f"duplicate supply delivery receipt: {delivery_id}")
        if delivery_id not in expected:
            raise DomainError(f"unexpected supply delivery receipt: {delivery_id}")
        if receipt.received_packages < 0:
            raise DomainError("received supply package count cannot be negative")
        seen.add(delivery_id)
        delivery = expected[delivery_id]
        variance = receipt.received_packages - delivery.expected_packages
        kind = ""
        if not receipt.seal_intact:
            kind = "seal_damaged"
        elif variance != 0:
            kind = "quantity_mismatch"
        elif receipt.received_at > delivery.window_end:
            kind = "late_arrival"
        elif receipt.received_at < delivery.window_start:
            kind = "early_arrival"
        if kind:
            findings.append(SupplyReceivingFinding(delivery_id, suppliers[delivery_id], kind, variance))
    for delivery_id, delivery in expected.items():
        if delivery_id not in seen and delivery.window_end < as_of:
            findings.append(
                SupplyReceivingFinding(
                    delivery_id, suppliers[delivery_id], "missing_receipt", -delivery.expected_packages
                )
            )
    priority = {"seal_damaged": 0, "missing_receipt": 1, "quantity_mismatch": 2, "late_arrival": 3, "early_arrival": 4}
    return sorted(findings, key=lambda item: (priority[item.kind], item.delivery_id))
