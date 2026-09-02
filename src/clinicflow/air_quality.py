"""Assess non-clinical room air-quality checks before opening."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class RoomAirReading:
    room_id: str
    observed_minute: int
    co2_ppm: int
    particulate_ug_m3: int


@dataclass(frozen=True, slots=True)
class RoomAirPolicy:
    room_id: str
    maximum_age_minutes: int
    maximum_co2_ppm: int
    maximum_particulate_ug_m3: int


@dataclass(frozen=True, slots=True)
class RoomAirFinding:
    room_id: str
    age_minutes: int
    stale: bool
    exceeded_metrics: tuple[str, ...]
    ready: bool


def assess_room_air_quality(
    readings: list[RoomAirReading], policies: list[RoomAirPolicy], now_minute: int
) -> list[RoomAirFinding]:
    """Use the latest reading for each room and report stale or exceeded checks."""
    if now_minute < 0:
        raise DomainError("air-quality assessment minute cannot be negative")
    configured: dict[str, RoomAirPolicy] = {}
    for policy in policies:
        room_id = clean_code(policy.room_id, "air policy room id")
        if room_id in configured:
            raise DomainError(f"duplicate room air policy: {room_id}")
        if min(policy.maximum_age_minutes, policy.maximum_co2_ppm, policy.maximum_particulate_ug_m3) < 1:
            raise DomainError("room air limits must be positive")
        configured[room_id] = policy

    latest: dict[str, RoomAirReading] = {}
    for reading in readings:
        room_id = clean_code(reading.room_id, "air reading room id")
        if room_id not in configured or reading.observed_minute > now_minute:
            raise DomainError("room air reading must reference a policy and cannot be in the future")
        if reading.co2_ppm < 0 or reading.particulate_ug_m3 < 0:
            raise DomainError("room air metrics cannot be negative")
        previous = latest.get(room_id)
        if previous is not None and previous.observed_minute == reading.observed_minute:
            raise DomainError(f"duplicate room air reading minute: {room_id}")
        if previous is None or reading.observed_minute > previous.observed_minute:
            latest[room_id] = reading

    findings: list[RoomAirFinding] = []
    for room_id, policy in configured.items():
        current = latest.get(room_id)
        if current is None:
            findings.append(RoomAirFinding(room_id, now_minute, True, ("missing",), False))
            continue
        age = now_minute - current.observed_minute
        exceeded = []
        if current.co2_ppm > policy.maximum_co2_ppm:
            exceeded.append("co2")
        if current.particulate_ug_m3 > policy.maximum_particulate_ug_m3:
            exceeded.append("particulate")
        stale = age > policy.maximum_age_minutes
        findings.append(RoomAirFinding(room_id, age, stale, tuple(exceeded), not stale and not exceeded))
    return sorted(findings, key=lambda item: (item.ready, -item.age_minutes, item.room_id))
