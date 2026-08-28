"""Demand-aware inventory reorder planning for clinic operations."""

from dataclasses import dataclass
from datetime import datetime
from math import ceil

from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class InventoryPosition:
    sku: str
    on_hand: int
    reserved: int
    safety_stock: int


@dataclass(frozen=True, slots=True)
class ScheduledConsumption:
    demand_id: str
    sku: str
    quantity: int
    needed_at: str


@dataclass(frozen=True, slots=True)
class SupplierOffer:
    sku: str
    supplier_id: str
    arrives_at: str
    pack_size: int
    maximum_packs: int


@dataclass(frozen=True, slots=True)
class ReorderRecommendation:
    sku: str
    supplier_id: str | None
    order_quantity: int
    arrives_at: str | None
    projected_shortage: int
    reason: str


def plan_inventory_reorders(
    positions: list[InventoryPosition],
    consumption: list[ScheduledConsumption],
    offers: list[SupplierOffer],
    horizon_at: str,
) -> list[ReorderRecommendation]:
    """Choose the earliest feasible pack order while preserving safety stock."""
    horizon = parse_time(horizon_at, "horizon_at")
    normalized_positions: dict[str, InventoryPosition] = {}
    for position in positions:
        sku = clean_code(position.sku, "inventory position sku")
        if sku in normalized_positions:
            raise DomainError(f"duplicate inventory position sku: {sku}")
        values = (position.on_hand, position.reserved, position.safety_stock)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
            raise DomainError("inventory position quantities must be non-negative integers")
        if position.reserved > position.on_hand:
            raise DomainError("inventory reserved quantity cannot exceed on_hand")
        normalized_positions[sku] = InventoryPosition(sku, *values)

    demand_by_sku: dict[str, int] = {}
    seen_demands: set[str] = set()
    for demand in consumption:
        demand_id = clean_code(demand.demand_id, "scheduled consumption id")
        if demand_id in seen_demands:
            raise DomainError(f"duplicate scheduled consumption id: {demand_id}")
        seen_demands.add(demand_id)
        sku = clean_code(demand.sku, "scheduled consumption sku")
        if sku not in normalized_positions:
            raise DomainError(f"consumption references unknown sku: {sku}")
        if isinstance(demand.quantity, bool) or not isinstance(demand.quantity, int) or demand.quantity < 1:
            raise DomainError("scheduled consumption quantity must be positive")
        if parse_time(demand.needed_at, "needed_at") <= horizon:
            demand_by_sku[sku] = demand_by_sku.get(sku, 0) + demand.quantity

    offers_by_sku: dict[str, list[tuple[SupplierOffer, datetime]]] = {}
    seen_offers: set[tuple[str, str]] = set()
    for offer in offers:
        sku = clean_code(offer.sku, "supplier offer sku")
        supplier_id = clean_code(offer.supplier_id, "supplier id")
        if (sku, supplier_id) in seen_offers:
            raise DomainError("duplicate supplier offer")
        seen_offers.add((sku, supplier_id))
        if sku not in normalized_positions:
            raise DomainError(f"offer references unknown sku: {sku}")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in (offer.pack_size, offer.maximum_packs)
        ):
            raise DomainError("supplier pack size and capacity must be positive integers")
        arrives_at = parse_time(offer.arrives_at, "arrives_at")
        offers_by_sku.setdefault(sku, []).append(
            (SupplierOffer(sku, supplier_id, offer.arrives_at, offer.pack_size, offer.maximum_packs), arrives_at)
        )

    recommendations: list[ReorderRecommendation] = []
    for sku, position in normalized_positions.items():
        shortage = max(0, position.reserved + demand_by_sku.get(sku, 0) + position.safety_stock - position.on_hand)
        if shortage == 0:
            continue
        candidates = sorted(offers_by_sku.get(sku, []), key=lambda item: (item[1], item[0].supplier_id))
        selected = next((offer for offer, arrives_at in candidates if arrives_at <= horizon), None)
        if selected is None:
            recommendations.append(
                ReorderRecommendation(sku, None, 0, None, shortage, "no supplier arrival within horizon")
            )
            continue
        packs = min(selected.maximum_packs, ceil(shortage / selected.pack_size))
        quantity = packs * selected.pack_size
        recommendations.append(
            ReorderRecommendation(
                sku,
                selected.supplier_id,
                quantity,
                selected.arrives_at,
                max(0, shortage - quantity),
                "supplier order planned",
            )
        )
    return sorted(recommendations, key=lambda item: (-item.projected_shortage, item.sku))
