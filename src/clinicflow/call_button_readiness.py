"""Assess non-clinical room assistance-call equipment."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class CallButtonPolicy:
    room_id: str
    maximum_response_seconds: int
    maximum_test_age_days: int
    backup_required: bool


@dataclass(frozen=True, slots=True)
class CallButtonCheck:
    room_id: str
    device_id: str
    response_seconds: int
    audible: bool
    visible: bool
    backup_available: bool
    tested_day: int


@dataclass(frozen=True, slots=True)
class CallButtonFinding:
    room_id: str
    response_ready: bool
    alert_ready: bool
    backup_ready: bool
    test_current: bool
    ready: bool


def assess_call_button_readiness(
    policies: list[CallButtonPolicy],
    checks: list[CallButtonCheck],
    current_day: int,
) -> list[CallButtonFinding]:
    """Verify response latency, dual alerts, backup, and test currency."""
    if current_day < 0:
        raise DomainError("call button current day is invalid")
    required: dict[str, CallButtonPolicy] = {}
    for policy in policies:
        room_id = clean_code(policy.room_id, "call button room id")
        if room_id in required or policy.maximum_response_seconds < 1 or policy.maximum_test_age_days < 0:
            raise DomainError("call button policy is duplicated or invalid")
        required[room_id] = CallButtonPolicy(
            room_id,
            policy.maximum_response_seconds,
            policy.maximum_test_age_days,
            policy.backup_required,
        )
    seen: set[str] = set()
    findings: list[CallButtonFinding] = []
    for check in checks:
        room_id = clean_code(check.room_id, "call button check room id")
        clean_code(check.device_id, "call button device id")
        matched = required.get(room_id)
        if (
            matched is None
            or room_id in seen
            or check.response_seconds < 0
            or check.tested_day < 0
            or check.tested_day > current_day
        ):
            raise DomainError("call button check is unknown, duplicated, or invalid")
        seen.add(room_id)
        response_ready = check.response_seconds <= matched.maximum_response_seconds
        alert_ready = check.audible and check.visible
        backup_ready = not matched.backup_required or check.backup_available
        test_current = current_day - check.tested_day <= matched.maximum_test_age_days
        findings.append(
            CallButtonFinding(
                room_id,
                response_ready,
                alert_ready,
                backup_ready,
                test_current,
                response_ready and alert_ready and backup_ready and test_current,
            )
        )
    if seen != set(required):
        raise DomainError("every call button policy needs a check")
    return sorted(findings, key=lambda item: (item.ready, item.room_id))
