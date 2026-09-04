"""Plan reception printer consumables for appointment operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .models import DomainError


@dataclass(frozen=True, slots=True)
class ReceptionPrintDemand:
    desk_id: str
    paper_sheets: int
    label_rolls: int
    priority: int


@dataclass(frozen=True, slots=True)
class ReceptionPrintStock:
    lot_id: str
    paper_sheets: int
    label_rolls: int
    expires_on: date


@dataclass(frozen=True, slots=True)
class ReceptionPrintAllocation:
    desk_id: str
    paper_allocated: int
    labels_allocated: int
    ready: bool


def _positive_integer(value: object, field: str, *, allow_zero: bool = True) -> int:
    minimum = 0 if allow_zero else 1
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise DomainError(f"{field} must be an integer of at least {minimum}")
    return value


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainError(f"{field} is required")
    return " ".join(value.split())


def allocate_reception_print_stock(
    demands: list[ReceptionPrintDemand], stock: list[ReceptionPrintStock], *, as_of: date
) -> list[ReceptionPrintAllocation]:
    """Allocate unexpired stock to higher-priority reception desks first."""
    if not isinstance(as_of, date):
        raise DomainError("reception print stock date is required")
    seen_lots: set[str] = set()
    available_paper = 0
    available_labels = 0
    for lot in stock:
        lot_id = _identifier(lot.lot_id, "reception print stock lot id")
        if lot_id.casefold() in seen_lots:
            raise DomainError(f"duplicate reception print stock lot {lot_id}")
        seen_lots.add(lot_id.casefold())
        paper = _positive_integer(lot.paper_sheets, "paper stock")
        labels = _positive_integer(lot.label_rolls, "label stock")
        if lot.expires_on >= as_of:
            available_paper += paper
            available_labels += labels
    seen_desks: set[str] = set()
    normalized: list[tuple[ReceptionPrintDemand, str]] = []
    for demand in demands:
        desk_id = _identifier(demand.desk_id, "reception desk id")
        if desk_id.casefold() in seen_desks:
            raise DomainError(f"duplicate reception print demand {desk_id}")
        seen_desks.add(desk_id.casefold())
        _positive_integer(demand.paper_sheets, "paper demand")
        _positive_integer(demand.label_rolls, "label demand")
        _positive_integer(demand.priority, "reception print priority", allow_zero=False)
        normalized.append((demand, desk_id))
    normalized.sort(key=lambda item: (-item[0].priority, item[1]))
    allocations: list[ReceptionPrintAllocation] = []
    for demand, desk_id in normalized:
        paper = min(available_paper, demand.paper_sheets)
        labels = min(available_labels, demand.label_rolls)
        available_paper -= paper
        available_labels -= labels
        allocations.append(
            ReceptionPrintAllocation(
                desk_id, paper, labels, paper == demand.paper_sheets and labels == demand.label_rolls
            )
        )
    return allocations
