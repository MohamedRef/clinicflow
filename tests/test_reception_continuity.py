import pytest

from clinicflow import (
    DomainError,
    ReceptionContinuityCheck,
    ReceptionContinuityRequirement,
    assess_reception_continuity,
)


def test_reception_continuity_reports_independent_shortfalls() -> None:
    got = assess_reception_continuity(
        [ReceptionContinuityRequirement("clinic", 100, 2, True)],
        [ReceptionContinuityCheck("clinic", 80, 1, False, 1)],
        40,
        30,
    )[0]
    assert got.form_shortfall == 20 and got.device_shortfall == 1
    assert not got.contact_ready and not got.rehearsal_current and not got.ready


def test_reception_continuity_accepts_complete_current_controls() -> None:
    got = assess_reception_continuity(
        [ReceptionContinuityRequirement("clinic", 100, 2, True)],
        [ReceptionContinuityCheck("clinic", 100, 2, True, 35)],
        40,
        30,
    )[0]
    assert got.ready


def test_reception_continuity_requires_every_check() -> None:
    with pytest.raises(DomainError, match="every"):
        assess_reception_continuity([ReceptionContinuityRequirement("clinic", 0, 0, False)], [], 1, 1)
