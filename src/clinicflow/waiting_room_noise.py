"""Assess waiting-room noise without handling clinical information."""

from dataclasses import dataclass

from clinicflow.models import DomainError, clean_text


@dataclass(frozen=True, slots=True)
class NoiseReading:
    zone_id: str
    decibels: int
    quiet_zone: bool
    mitigation_available: bool
    measured_minutes_ago: int


@dataclass(frozen=True, slots=True)
class WaitingRoomNoiseFinding:
    zone_id: str
    state: str
    reasons: tuple[str, ...]
    priority: int


def assess_waiting_room_noise(
    readings: list[NoiseReading],
    *,
    standard_limit: int = 65,
    quiet_limit: int = 50,
    stale_after_minutes: int = 30,
) -> list[WaitingRoomNoiseFinding]:
    """Prioritize stale or excessive waiting-room noise readings."""
    if not 1 <= quiet_limit <= standard_limit <= 120:
        raise DomainError("noise limits must be ordered between 1 and 120 decibels")
    if stale_after_minutes < 1:
        raise DomainError("stale threshold must be positive")

    seen: set[str] = set()
    findings: list[WaitingRoomNoiseFinding] = []
    for reading in readings:
        zone_id = clean_text(reading.zone_id, "waiting room zone", 80)
        key = zone_id.casefold()
        if key in seen:
            raise DomainError("duplicate waiting room zone")
        seen.add(key)
        if not 0 <= reading.decibels <= 140:
            raise DomainError("noise reading must be between 0 and 140 decibels")
        if reading.measured_minutes_ago < 0:
            raise DomainError("noise reading age cannot be negative")

        reasons: list[str] = []
        limit = quiet_limit if reading.quiet_zone else standard_limit
        if reading.measured_minutes_ago > stale_after_minutes:
            reasons.append("reading_stale")
        if reading.decibels > limit:
            reasons.append("limit_exceeded")
            if not reading.mitigation_available:
                reasons.append("mitigation_unavailable")

        if "mitigation_unavailable" in reasons:
            state = "relocate"
            priority = 300 + reading.decibels - limit
        elif "limit_exceeded" in reasons:
            state = "mitigate"
            priority = 200 + reading.decibels - limit
        elif "reading_stale" in reasons:
            state = "remeasure"
            priority = 100 + reading.measured_minutes_ago - stale_after_minutes
        else:
            state = "acceptable"
            priority = 0
        findings.append(WaitingRoomNoiseFinding(zone_id, state, tuple(reasons), priority))

    return sorted(findings, key=lambda row: (-row.priority, row.zone_id.casefold()))
