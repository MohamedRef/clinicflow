"""Appointment accessibility readiness from time-bounded room checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .models import DomainError, clean_code, clean_codes, parse_time


class AccessibilityDisposition(StrEnum):
    READY = "ready"
    MISSING_FEATURES = "missing-features"
    STALE_CHECK = "stale-check"
    UNASSESSED = "unassessed"


@dataclass(frozen=True, slots=True)
class AppointmentAccessibilityNeed:
    appointment_id: str
    room_id: str
    arrives_at: str
    required_features: set[str]


@dataclass(frozen=True, slots=True)
class RoomAccessibilityCheck:
    room_id: str
    checked_at: str
    valid_until: str
    available_features: set[str]
    unavailable_features: set[str]


@dataclass(frozen=True, slots=True)
class AccessibilityAssessment:
    appointment_id: str
    room_id: str
    disposition: AccessibilityDisposition
    missing_features: tuple[str, ...]
    evidence_checked_at: str | None


def assess_accessibility_readiness(
    needs: list[AppointmentAccessibilityNeed], checks: list[RoomAccessibilityCheck]
) -> list[AccessibilityAssessment]:
    """Assess each appointment against the latest check valid at arrival."""
    checks_by_room: dict[str, list[tuple[datetime, datetime, RoomAccessibilityCheck]]] = {}
    check_keys: set[tuple[str, datetime]] = set()
    for check in checks:
        room_id = clean_code(check.room_id, "room id")
        checked_at = parse_time(check.checked_at, "checked_at")
        valid_until = parse_time(check.valid_until, "valid_until")
        if valid_until <= checked_at:
            raise DomainError("accessibility valid_until must follow checked_at")
        key = (room_id, checked_at)
        if key in check_keys:
            raise DomainError(f"duplicate accessibility check: {room_id} at {checked_at.isoformat()}")
        check_keys.add(key)
        available = clean_codes(check.available_features, "available accessibility feature")
        unavailable = clean_codes(check.unavailable_features, "unavailable accessibility feature")
        overlap = available & unavailable
        if overlap:
            raise DomainError(f"accessibility features cannot be both available and unavailable: {sorted(overlap)}")
        normalized = RoomAccessibilityCheck(
            room_id,
            check.checked_at,
            check.valid_until,
            available,
            unavailable,
        )
        checks_by_room.setdefault(room_id, []).append((checked_at, valid_until, normalized))
    for room_checks in checks_by_room.values():
        room_checks.sort(key=lambda row: row[0])

    seen_needs: set[str] = set()
    assessments: list[AccessibilityAssessment] = []
    for need in needs:
        appointment_id = clean_code(need.appointment_id, "appointment id")
        if appointment_id in seen_needs:
            raise DomainError(f"duplicate accessibility appointment id: {appointment_id}")
        seen_needs.add(appointment_id)
        room_id = clean_code(need.room_id, "room id")
        arrives_at = parse_time(need.arrives_at, "arrives_at")
        required = clean_codes(need.required_features, "required accessibility feature")
        room_checks = checks_by_room.get(room_id, [])
        valid = [row for row in room_checks if row[0] <= arrives_at < row[1]]
        if valid:
            _, _, latest = valid[-1]
            missing = tuple(sorted(required - latest.available_features))
            disposition = AccessibilityDisposition.MISSING_FEATURES if missing else AccessibilityDisposition.READY
            evidence = latest.checked_at
        elif room_checks:
            missing = tuple(sorted(required))
            disposition = AccessibilityDisposition.STALE_CHECK
            evidence = room_checks[-1][2].checked_at
        else:
            missing = tuple(sorted(required))
            disposition = AccessibilityDisposition.UNASSESSED
            evidence = None
        assessments.append(
            AccessibilityAssessment(
                appointment_id,
                room_id,
                disposition,
                missing,
                evidence,
            )
        )
    return sorted(assessments, key=lambda assessment: assessment.appointment_id)
