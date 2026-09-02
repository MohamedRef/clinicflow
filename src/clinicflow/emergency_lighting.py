"""Assess emergency-lighting inspection coverage for clinic zones."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class EmergencyLightingPolicy:
    clinic_id: str
    maximum_test_age_days: int
    minimum_battery_minutes: int


@dataclass(frozen=True, slots=True)
class EmergencyLightingCheck:
    clinic_id: str
    zone_id: str
    tested_day: int
    battery_minutes: int
    illuminates_exit_route: bool


@dataclass(frozen=True, slots=True)
class EmergencyLightingFinding:
    clinic_id: str
    zone_id: str
    test_current: bool
    battery_ready: bool
    exit_route_ready: bool
    ready: bool


def assess_emergency_lighting(
    policies: list[EmergencyLightingPolicy],
    checks: list[EmergencyLightingCheck],
    current_day: int,
) -> list[EmergencyLightingFinding]:
    """Return unsafe zones first using deterministic day-based inspection ages."""
    if current_day < 0:
        raise DomainError("current lighting assessment day cannot be negative")
    by_clinic: dict[str, EmergencyLightingPolicy] = {}
    for policy in policies:
        clinic_id = clean_code(policy.clinic_id, "lighting policy clinic id")
        if clinic_id in by_clinic:
            raise DomainError(f"duplicate emergency lighting policy: {clinic_id}")
        if policy.maximum_test_age_days < 0 or policy.minimum_battery_minutes < 1:
            raise DomainError("emergency lighting policy has invalid thresholds")
        by_clinic[clinic_id] = EmergencyLightingPolicy(
            clinic_id,
            policy.maximum_test_age_days,
            policy.minimum_battery_minutes,
        )

    seen: set[tuple[str, str]] = set()
    findings: list[EmergencyLightingFinding] = []
    for check in checks:
        clinic_id = clean_code(check.clinic_id, "lighting check clinic id")
        zone_id = clean_code(check.zone_id, "lighting zone id")
        clinic_policy = by_clinic.get(clinic_id)
        if clinic_policy is None:
            raise DomainError(f"emergency lighting policy missing: {clinic_id}")
        key = (clinic_id, zone_id)
        if key in seen:
            raise DomainError(f"duplicate emergency lighting check: {clinic_id}/{zone_id}")
        if check.tested_day < 0 or check.tested_day > current_day or check.battery_minutes < 0:
            raise DomainError("emergency lighting check has invalid measurements")
        seen.add(key)
        test_current = current_day - check.tested_day <= clinic_policy.maximum_test_age_days
        battery_ready = check.battery_minutes >= clinic_policy.minimum_battery_minutes
        ready = test_current and battery_ready and check.illuminates_exit_route
        findings.append(
            EmergencyLightingFinding(
                clinic_id,
                zone_id,
                test_current,
                battery_ready,
                check.illuminates_exit_route,
                ready,
            )
        )
    return sorted(
        findings,
        key=lambda item: (
            item.ready,
            item.test_current,
            item.battery_ready,
            item.clinic_id,
            item.zone_id,
        ),
    )
