import pytest

from clinicflow import CallButtonCheck, CallButtonPolicy, DomainError, assess_call_button_readiness


def test_call_button_readiness_reports_independent_failures() -> None:
    policies = [CallButtonPolicy("room", 10, 30, True)]
    checks = [CallButtonCheck("room", "button", 12, True, False, False, 1)]
    got = assess_call_button_readiness(policies, checks, 40)[0]
    assert not got.response_ready
    assert not got.alert_ready and not got.backup_ready and not got.test_current
    assert not got.ready


def test_call_button_readiness_accepts_current_dual_alert() -> None:
    got = assess_call_button_readiness(
        [CallButtonPolicy("room", 10, 30, True)],
        [CallButtonCheck("room", "button", 5, True, True, True, 35)],
        40,
    )[0]
    assert got.ready


def test_call_button_readiness_requires_every_room_check() -> None:
    with pytest.raises(DomainError, match="every"):
        assess_call_button_readiness([CallButtonPolicy("room", 10, 30, False)], [], 40)
