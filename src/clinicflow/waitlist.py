"""Deterministic waitlist matching for released appointment slots."""

from dataclasses import dataclass
from datetime import datetime

from .models import DomainError, clean_code, clean_codes, clean_text, parse_time


@dataclass(frozen=True, slots=True)
class WaitlistRequest:
    id: str
    patient_reference: str
    procedure: str
    required_capabilities: set[str]
    earliest_at: str
    latest_at: str
    priority: int


@dataclass(frozen=True, slots=True)
class ReleasedSlot:
    id: str
    room_id: str
    capabilities: set[str]
    starts_at: str
    ends_at: str


@dataclass(frozen=True, slots=True)
class WaitlistMatch:
    request_id: str
    slot_id: str
    patient_reference: str


def match_waitlist(requests: list[WaitlistRequest], slots: list[ReleasedSlot]) -> list[WaitlistMatch]:
    """Match highest-priority eligible requests to chronological released slots."""
    normalized_requests: list[tuple[WaitlistRequest, datetime, datetime]] = []
    seen_requests: set[str] = set()
    for request in requests:
        request_id = clean_code(request.id, "waitlist request id")
        if request_id in seen_requests:
            raise DomainError(f"duplicate waitlist request id: {request_id}")
        seen_requests.add(request_id)
        earliest = parse_time(request.earliest_at, "earliest_at")
        latest = parse_time(request.latest_at, "latest_at")
        if latest <= earliest or isinstance(request.priority, bool) or not 1 <= request.priority <= 5:
            raise DomainError("waitlist window and priority must be valid")
        normalized_requests.append(
            (
                WaitlistRequest(
                    request_id,
                    clean_text(request.patient_reference, "patient reference", 120),
                    clean_text(request.procedure, "procedure", 160),
                    clean_codes(request.required_capabilities, "required capability"),
                    request.earliest_at,
                    request.latest_at,
                    request.priority,
                ),
                earliest,
                latest,
            )
        )
    normalized_slots: list[tuple[ReleasedSlot, datetime, datetime]] = []
    seen_slots: set[str] = set()
    for slot in slots:
        slot_id = clean_code(slot.id, "released slot id")
        if slot_id in seen_slots:
            raise DomainError(f"duplicate released slot id: {slot_id}")
        seen_slots.add(slot_id)
        starts = parse_time(slot.starts_at, "starts_at")
        ends = parse_time(slot.ends_at, "ends_at")
        if ends <= starts:
            raise DomainError("released slot ends_at must follow starts_at")
        normalized_slots.append((slot, starts, ends))

    remaining = sorted(
        normalized_requests,
        key=lambda item: (-item[0].priority, item[2], item[0].id),
    )
    matches: list[WaitlistMatch] = []
    for slot, starts, ends in sorted(normalized_slots, key=lambda item: (item[1], item[0].id)):
        match = next(
            (
                item
                for item in remaining
                if item[1] <= starts and ends <= item[2] and item[0].required_capabilities <= slot.capabilities
            ),
            None,
        )
        if match is None:
            continue
        request = match[0]
        matches.append(WaitlistMatch(request.id, slot.id, request.patient_reference))
        remaining.remove(match)
    return matches
