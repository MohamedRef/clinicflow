"""Schedule inbound clinic supplies through constrained delivery docks."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class DeliveryDockWindow:
    dock_id: str
    opens_at: str
    closes_at: str
    pallet_limit: int
    refrigerated: bool


@dataclass(frozen=True, slots=True)
class SupplyDeliveryRequest:
    delivery_id: str
    ready_at: str
    pallets: int
    unloading_minutes: int
    refrigerated: bool
    priority: int


@dataclass(frozen=True, slots=True)
class DockDeliveryAssignment:
    delivery_id: str
    dock_id: str | None
    starts_at: str | None
    assigned: bool
    reason: str


def schedule_delivery_docks(
    windows: list[DeliveryDockWindow], deliveries: list[SupplyDeliveryRequest]
) -> list[DockDeliveryAssignment]:
    """Reserve earliest compatible dock time for priority-ranked inbound supplies."""
    capacity: dict[str, tuple[DeliveryDockWindow, datetime, datetime, datetime]] = {}
    for window in windows:
        dock_id = clean_code(window.dock_id, "delivery dock id")
        if dock_id.casefold() in capacity:
            raise DomainError(f"duplicate delivery dock: {dock_id}")
        opens = parse_time(window.opens_at, "opens_at")
        closes = parse_time(window.closes_at, "closes_at")
        if closes <= opens:
            raise DomainError("delivery dock window must be ordered")
        if isinstance(window.pallet_limit, bool) or not 1 <= window.pallet_limit <= 200:
            raise DomainError("dock pallet limit must be from 1 through 200")
        capacity[dock_id.casefold()] = (window, opens, closes, opens)
    seen: set[str] = set()
    normalized: list[tuple[SupplyDeliveryRequest, datetime]] = []
    for delivery in deliveries:
        delivery_id = clean_code(delivery.delivery_id, "supply delivery id")
        if delivery_id.casefold() in seen:
            raise DomainError(f"duplicate supply delivery: {delivery_id}")
        seen.add(delivery_id.casefold())
        if isinstance(delivery.pallets, bool) or not 1 <= delivery.pallets <= 200:
            raise DomainError("delivery pallets must be from 1 through 200")
        if isinstance(delivery.unloading_minutes, bool) or not 5 <= delivery.unloading_minutes <= 480:
            raise DomainError("unloading minutes must be from 5 through 480")
        if isinstance(delivery.priority, bool) or not 1 <= delivery.priority <= 5:
            raise DomainError("delivery priority must be from 1 through 5")
        normalized.append(
            (
                SupplyDeliveryRequest(
                    delivery_id,
                    delivery.ready_at,
                    delivery.pallets,
                    delivery.unloading_minutes,
                    delivery.refrigerated,
                    delivery.priority,
                ),
                parse_time(delivery.ready_at, "ready_at"),
            )
        )
    assignments: list[DockDeliveryAssignment] = []
    for delivery, ready_at in sorted(normalized, key=lambda row: (-row[0].priority, row[1], row[0].delivery_id)):
        candidates: list[tuple[datetime, str]] = []
        for key, (window, opens, closes, next_at) in capacity.items():
            start = max(opens, next_at, ready_at)
            end = start + timedelta(minutes=delivery.unloading_minutes)
            if (
                window.pallet_limit >= delivery.pallets
                and (not delivery.refrigerated or window.refrigerated)
                and end <= closes
            ):
                candidates.append((start, key))
        if not candidates:
            assignments.append(
                DockDeliveryAssignment(delivery.delivery_id, None, None, False, "no compatible dock capacity")
            )
            continue
        start, key = min(candidates, key=lambda row: (row[0], capacity[row[1]][0].dock_id))
        window, opens, closes, _ = capacity[key]
        capacity[key] = (window, opens, closes, start + timedelta(minutes=delivery.unloading_minutes))
        assignments.append(
            DockDeliveryAssignment(
                delivery.delivery_id, window.dock_id, start.isoformat(), True, "earliest compatible dock reserved"
            )
        )
    return assignments
