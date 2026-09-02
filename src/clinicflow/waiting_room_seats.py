"""Allocate waiting-room seating while preserving accessible capacity."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class WaitingRoomZone:
    zone_id: str
    clinic_id: str
    standard_seats: int
    accessible_seats: int
    open: bool


@dataclass(frozen=True, slots=True)
class WaitingParty:
    party_id: str
    clinic_id: str
    party_size: int
    accessible_seats: int
    priority: int


@dataclass(frozen=True, slots=True)
class WaitingSeatAllocation:
    party_id: str
    zone_id: str | None
    assigned: bool
    reason: str


def allocate_waiting_room_seats(
    zones: list[WaitingRoomZone],
    parties: list[WaitingParty],
) -> list[WaitingSeatAllocation]:
    """Assign priority parties to the smallest compatible open zone."""
    zone_ids: set[str] = set()
    inventory: list[dict[str, str | int]] = []
    for zone in zones:
        zone_id = clean_code(zone.zone_id, "waiting zone id")
        clinic_id = clean_code(zone.clinic_id, "waiting zone clinic id")
        if (
            zone_id in zone_ids
            or zone.standard_seats < 0
            or zone.accessible_seats < 0
            or zone.standard_seats + zone.accessible_seats == 0
        ):
            raise DomainError("waiting room zone is duplicated or invalid")
        zone_ids.add(zone_id)
        inventory.append(
            {
                "zone_id": zone_id,
                "clinic_id": clinic_id,
                "standard": zone.standard_seats if zone.open else 0,
                "accessible": zone.accessible_seats if zone.open else 0,
            }
        )
    party_ids: set[str] = set()
    normalized: list[WaitingParty] = []
    for party in parties:
        party_id = clean_code(party.party_id, "waiting party id")
        clinic_id = clean_code(party.clinic_id, "waiting party clinic id")
        if (
            party_id in party_ids
            or party.party_size < 1
            or party.accessible_seats < 0
            or party.accessible_seats > party.party_size
            or party.priority < 0
        ):
            raise DomainError("waiting party is duplicated or invalid")
        party_ids.add(party_id)
        normalized.append(WaitingParty(party_id, clinic_id, party.party_size, party.accessible_seats, party.priority))
    allocations: list[WaitingSeatAllocation] = []
    for party in sorted(normalized, key=lambda item: (-item.priority, item.party_id)):
        standard_needed = party.party_size - party.accessible_seats
        candidates = sorted(
            (
                zone
                for zone in inventory
                if zone["clinic_id"] == party.clinic_id
                and int(zone["standard"]) >= standard_needed
                and int(zone["accessible"]) >= party.accessible_seats
            ),
            key=lambda zone: (
                int(zone["standard"]) + int(zone["accessible"]),
                str(zone["zone_id"]),
            ),
        )
        if not candidates:
            allocations.append(WaitingSeatAllocation(party.party_id, None, False, "no_capacity"))
            continue
        selected = candidates[0]
        selected["standard"] = int(selected["standard"]) - standard_needed
        selected["accessible"] = int(selected["accessible"]) - party.accessible_seats
        allocations.append(WaitingSeatAllocation(party.party_id, str(selected["zone_id"]), True, "assigned"))
    return allocations
