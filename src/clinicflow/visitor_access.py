"""Vendor and visitor access scheduling for non-clinical clinic operations."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import DomainError, clean_code, clean_text, parse_time


@dataclass(frozen=True, slots=True)
class VisitorAccessRequest:
    request_id: str
    visitor: str
    sponsor: str
    starts_at: str
    ends_at: str
    zones: tuple[str, ...]
    credential_expires_at: str
    safety_trained_at: str


@dataclass(frozen=True, slots=True)
class AccessDeskWindow:
    window_id: str
    opens_at: str
    closes_at: str
    supported_zones: tuple[str, ...]
    capacity: int


@dataclass(frozen=True, slots=True)
class VisitorAccessAssignment:
    request_id: str
    window_id: str | None
    assigned: bool
    reason: str


def schedule_visitor_access(
    requests: list[VisitorAccessRequest],
    windows: list[AccessDeskWindow],
    assessed_at: str,
    maximum_training_age_days: int = 365,
) -> list[VisitorAccessAssignment]:
    """Schedule credential issue only when sponsorship, training, and zone coverage are valid."""
    now = parse_time(assessed_at, "assessed_at")
    if (
        isinstance(maximum_training_age_days, bool)
        or not isinstance(maximum_training_age_days, int)
        or not 1 <= maximum_training_age_days <= 730
    ):
        raise DomainError("maximum training age must be from 1 through 730 days")
    indexed: dict[str, tuple[AccessDeskWindow, datetime, datetime, set[str]]] = {}
    remaining: dict[str, int] = {}
    for window in windows:
        window_id = clean_code(window.window_id, "access window id")
        key = window_id.casefold()
        if key in indexed:
            raise DomainError(f"duplicate access window id: {window_id}")
        opens_at = parse_time(window.opens_at, "opens_at")
        closes_at = parse_time(window.closes_at, "closes_at")
        if closes_at <= opens_at:
            raise DomainError(f"access window {window_id} must be ordered")
        if isinstance(window.capacity, bool) or not isinstance(window.capacity, int) or window.capacity < 1:
            raise DomainError("access window capacity must be positive")
        zones = _zones(window.supported_zones, "supported zone")
        indexed[key] = (window, opens_at, closes_at, zones)
        remaining[key] = window.capacity
    normalized: list[tuple[VisitorAccessRequest, datetime, datetime, datetime, datetime, set[str]]] = []
    seen: set[str] = set()
    for request in requests:
        request_id = clean_code(request.request_id, "visitor request id")
        if request_id.casefold() in seen:
            raise DomainError(f"duplicate visitor request id: {request_id}")
        seen.add(request_id.casefold())
        clean_text(request.visitor, "visitor")
        clean_text(request.sponsor, "visitor sponsor")
        starts_at = parse_time(request.starts_at, "starts_at")
        ends_at = parse_time(request.ends_at, "ends_at")
        credential_expires = parse_time(request.credential_expires_at, "credential_expires_at")
        trained_at = parse_time(request.safety_trained_at, "safety_trained_at")
        if ends_at <= starts_at:
            raise DomainError(f"visitor request {request_id} must be ordered")
        if trained_at > now:
            raise DomainError(f"visitor request {request_id} training cannot be in the future")
        normalized.append(
            (request, starts_at, ends_at, credential_expires, trained_at, _zones(request.zones, "requested zone"))
        )
    normalized.sort(key=lambda row: (row[1], row[0].request_id))
    assignments: list[VisitorAccessAssignment] = []
    maximum_age = timedelta(days=maximum_training_age_days)
    for request, starts_at, ends_at, credential_expires, trained_at, zones in normalized:
        if credential_expires < ends_at:
            assignments.append(
                VisitorAccessAssignment(request.request_id, None, False, "credential expires before visit ends")
            )
            continue
        if starts_at - trained_at > maximum_age:
            assignments.append(VisitorAccessAssignment(request.request_id, None, False, "safety training is stale"))
            continue
        candidates = [
            (opens_at, key)
            for key, (_, opens_at, closes_at, supported) in indexed.items()
            if remaining[key] > 0 and opens_at <= starts_at and closes_at >= starts_at and zones <= supported
        ]
        if not candidates:
            assignments.append(
                VisitorAccessAssignment(request.request_id, None, False, "no access desk covers the visit zones")
            )
            continue
        _, selected = max(candidates, key=lambda row: (row[0], indexed[row[1]][0].window_id))
        remaining[selected] -= 1
        assignments.append(
            VisitorAccessAssignment(
                request.request_id, indexed[selected][0].window_id, True, "latest compatible credential window"
            )
        )
    return assignments


def _zones(values: tuple[str, ...], field: str) -> set[str]:
    zones = {clean_code(value, field).casefold() for value in values}
    if not zones or len(zones) != len(values):
        raise DomainError(f"{field}s must be non-empty and unique")
    return zones
