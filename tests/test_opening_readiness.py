from dataclasses import replace

import pytest

from clinicflow import ClinicOpeningAssessment, DomainError, OpeningCheck, OpeningCheckStatus, assess_clinic_opening


def check(identifier: str, category: str) -> OpeningCheck:
    return OpeningCheck(
        identifier,
        category,
        "Operations Lead",
        "2026-09-02T07:00:00+02:00",
        OpeningCheckStatus.VERIFIED,
        "2026-09-02T07:30:00+02:00",
        "Duty Manager",
        f"evidence://{identifier}",
    )


def test_requires_complete_cross_functional_opening_coverage() -> None:
    rows = [
        check("rooms", "rooms"),
        check("staff", "staffing"),
        check("stock", "inventory"),
        check("facility", "facilities"),
    ]
    result = assess_clinic_opening(rows, "2026-09-02T08:00:00+02:00")
    assert result == ClinicOpeningAssessment(True, (), (), (), ())


def test_reports_pending_and_missing_opening_work() -> None:
    pending = OpeningCheck(
        "rooms", "rooms", "Operations Lead", "2026-09-02T07:00:00+02:00", OpeningCheckStatus.PENDING, None, None, None
    )
    result = assess_clinic_opening([pending], "2026-09-02T08:00:00+02:00")
    assert result.ready is False
    assert result.pending_check_ids == ("rooms",)
    assert result.missing_categories == ("facilities", "inventory", "rooms", "staffing")


def test_requires_independent_accountable_waivers() -> None:
    waived = replace(
        check("facility", "facilities"),
        status=OpeningCheckStatus.WAIVED,
        completed_by="operations lead",
        evidence=None,
        waiver_reason="Approved contingency",
    )
    with pytest.raises(DomainError, match="independent"):
        assess_clinic_opening([waived], "2026-09-02T08:00:00+02:00")
    with pytest.raises(DomainError, match="duplicate opening check"):
        assess_clinic_opening([check("Same", "rooms"), check("same", "rooms")], "2026-09-02T08:00:00+02:00")
