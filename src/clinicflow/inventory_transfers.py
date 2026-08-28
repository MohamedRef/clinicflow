"""Cross-room inventory transfers for time-bound clinic demand."""

from dataclasses import dataclass
from datetime import datetime

from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class RoomStock:
    lot_id: str
    room_id: str
    sku: str
    quantity: int
    reserved_quantity: int
    available_at: str
    expires_at: str


@dataclass(frozen=True, slots=True)
class TransferRequest:
    request_id: str
    destination_room_id: str
    sku: str
    quantity: int
    needed_at: str


@dataclass(frozen=True, slots=True)
class StockTransfer:
    request_id: str
    lot_id: str
    source_room_id: str
    destination_room_id: str
    sku: str
    quantity: int


@dataclass(frozen=True, slots=True)
class TransferShortage:
    request_id: str
    sku: str
    missing_quantity: int


def plan_inventory_transfers(
    requests: list[TransferRequest], stocks: list[RoomStock]
) -> tuple[list[StockTransfer], list[TransferShortage]]:
    """Allocate transferable room stock by expiry and chronological demand."""
    remaining, normalized_stocks = _normalize_stocks(stocks)
    normalized_requests = _normalize_requests(requests)
    transfers: list[StockTransfer] = []
    shortages: list[TransferShortage] = []
    for request, needed_at in normalized_requests:
        missing = request.quantity
        for stock, available_at, expires_at in normalized_stocks:
            if not _can_supply(stock, request, available_at, expires_at, needed_at, remaining):
                continue
            quantity = min(missing, remaining[stock.lot_id])
            remaining[stock.lot_id] -= quantity
            missing -= quantity
            transfers.append(
                StockTransfer(
                    request.request_id,
                    stock.lot_id,
                    stock.room_id,
                    request.destination_room_id,
                    request.sku,
                    quantity,
                )
            )
            if missing == 0:
                break
        if missing:
            shortages.append(TransferShortage(request.request_id, request.sku, missing))
    return transfers, shortages


def _normalize_stocks(
    stocks: list[RoomStock],
) -> tuple[dict[str, int], list[tuple[RoomStock, datetime, datetime]]]:
    remaining: dict[str, int] = {}
    normalized: list[tuple[RoomStock, datetime, datetime]] = []
    seen: set[str] = set()
    for stock in stocks:
        lot_id = clean_code(stock.lot_id, "transfer lot id")
        key = lot_id.casefold()
        if key in seen:
            raise DomainError(f"duplicate transfer lot id: {lot_id}")
        seen.add(key)
        room_id = clean_code(stock.room_id, "stock room id")
        sku = clean_code(stock.sku, "stock sku")
        quantity = _quantity(stock.quantity, "stock quantity", allow_zero=True)
        reserved = _quantity(stock.reserved_quantity, "reserved quantity", allow_zero=True)
        if reserved > quantity:
            raise DomainError("reserved quantity cannot exceed stock quantity")
        available_at = parse_time(stock.available_at, "available_at")
        expires_at = parse_time(stock.expires_at, "expires_at")
        if expires_at <= available_at:
            raise DomainError("stock expiry must be later than availability")
        normalized_stock = RoomStock(
            lot_id,
            room_id,
            sku,
            quantity,
            reserved,
            stock.available_at,
            stock.expires_at,
        )
        remaining[lot_id] = quantity - reserved
        normalized.append((normalized_stock, available_at, expires_at))
    normalized.sort(key=lambda item: (item[2], item[0].room_id, item[0].lot_id))
    return remaining, normalized


def _normalize_requests(requests: list[TransferRequest]) -> list[tuple[TransferRequest, datetime]]:
    normalized: list[tuple[TransferRequest, datetime]] = []
    seen: set[str] = set()
    for request in requests:
        request_id = clean_code(request.request_id, "transfer request id")
        key = request_id.casefold()
        if key in seen:
            raise DomainError(f"duplicate transfer request id: {request_id}")
        seen.add(key)
        destination = clean_code(request.destination_room_id, "destination room id")
        sku = clean_code(request.sku, "request sku")
        quantity = _quantity(request.quantity, "request quantity", allow_zero=False)
        needed_at = parse_time(request.needed_at, "needed_at")
        normalized.append((TransferRequest(request_id, destination, sku, quantity, request.needed_at), needed_at))
    normalized.sort(key=lambda item: (item[1], item[0].request_id))
    return normalized


def _can_supply(
    stock: RoomStock,
    request: TransferRequest,
    available_at: datetime,
    expires_at: datetime,
    needed_at: datetime,
    remaining: dict[str, int],
) -> bool:
    return (
        stock.sku == request.sku
        and stock.room_id.casefold() != request.destination_room_id.casefold()
        and available_at <= needed_at < expires_at
        and remaining[stock.lot_id] > 0
    )


def _quantity(value: int, field: str, *, allow_zero: bool) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= 1_000_000:
        raise DomainError(f"{field} must be from {minimum} through 1000000")
    return value
