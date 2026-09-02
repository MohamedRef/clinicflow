import pytest

from clinicflow import (
    DomainError,
    EmergencyLightingCheck,
    EmergencyLightingPolicy,
    assess_emergency_lighting,
)


def test_emergency_lighting_reports_stale_and_low_battery_zones() -> None:
    policy = EmergencyLightingPolicy("clinic", 30, 90)
    got = assess_emergency_lighting(
        [policy],
        [
            EmergencyLightingCheck("clinic", "ready", 90, 120, True),
            EmergencyLightingCheck("clinic", "unsafe", 60, 45, True),
        ],
        100,
    )
    assert got[0].zone_id == "unsafe"
    assert not got[0].test_current
    assert not got[0].battery_ready
    assert got[1].ready


def test_emergency_lighting_rejects_future_tests() -> None:
    with pytest.raises(DomainError, match="invalid measurements"):
        assess_emergency_lighting(
            [EmergencyLightingPolicy("clinic", 30, 90)],
            [EmergencyLightingCheck("clinic", "zone", 101, 90, True)],
            100,
        )


def test_emergency_lighting_requires_a_clinic_policy() -> None:
    with pytest.raises(DomainError, match="policy missing"):
        assess_emergency_lighting(
            [],
            [EmergencyLightingCheck("clinic", "zone", 10, 90, True)],
            10,
        )
