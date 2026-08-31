"""Assess clean-linen par levels for clinic rooms."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class RoomLinenPosition:
    room_id: str
    linen_type: str
    clean_on_hand: int
    reserved: int
    par_level: int


@dataclass(frozen=True, slots=True)
class LinenReplenishment:
    room_id: str
    linen_type: str
    usable: int
    par_level: int
    replenish_quantity: int


def plan_linen_replenishment(positions: list[RoomLinenPosition]) -> list[LinenReplenishment]:
    """Return room-level replenishment needed after existing reservations."""
    seen: set[tuple[str, str]] = set()
    replenishments: list[LinenReplenishment] = []
    for position in positions:
        room_id = clean_code(position.room_id, "linen room id")
        linen_type = clean_code(position.linen_type, "linen type").lower()
        key = (room_id, linen_type)
        if key in seen:
            raise DomainError(f"duplicate room linen position: {room_id}/{linen_type}")
        seen.add(key)
        values = (position.clean_on_hand, position.reserved, position.par_level)
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
            raise DomainError("linen quantities must be non-negative integers")
        if position.reserved > position.clean_on_hand:
            raise DomainError("reserved linen cannot exceed clean stock")
        usable = position.clean_on_hand - position.reserved
        if usable < position.par_level:
            replenishments.append(
                LinenReplenishment(room_id, linen_type, usable, position.par_level, position.par_level - usable)
            )
    return sorted(replenishments, key=lambda item: (-item.replenish_quantity, item.room_id, item.linen_type))
