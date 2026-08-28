"""Public behavior tests for staff absence coverage."""

import pytest

from clinicflow import CoverageDemand, SubstituteStaff, assign_staff_coverage
from clinicflow.models import DomainError


def demand(identifier: str, starts_at: str, priority: int, qualifications: set[str]) -> CoverageDemand:
    return CoverageDemand(
        identifier,
        "absent",
        starts_at,
        starts_at.replace(":00:00", ":30:00"),
        qualifications,
        priority,
    )


def test_assigns_priority_coverage_without_double_booking() -> None:
    substitutes = [
        SubstituteStaff(
            "staff-a", {"triage", "inventory"}, "2026-09-01T08:00:00+00:00", "2026-09-01T17:00:00+00:00", 2
        ),
        SubstituteStaff("staff-b", {"triage"}, "2026-09-01T08:00:00+00:00", "2026-09-01T17:00:00+00:00", 2),
    ]
    rows = assign_staff_coverage(
        [
            demand("routine", "2026-09-01T09:00:00+00:00", 1, {"triage"}),
            demand("urgent", "2026-09-01T09:00:00+00:00", 5, {"triage", "inventory"}),
            demand("later", "2026-09-01T10:00:00+00:00", 3, {"triage"}),
        ],
        substitutes,
    )
    assert [(row.appointment_id, row.substitute_staff_id) for row in rows] == [
        ("urgent", "staff-a"),
        ("later", "staff-b"),
        ("routine", "staff-b"),
    ]


def test_reports_uncovered_qualification_requirements() -> None:
    rows = assign_staff_coverage(
        [demand("imaging", "2026-09-01T09:00:00+00:00", 5, {"imaging"})],
        [SubstituteStaff("staff", {"triage"}, "2026-09-01T08:00:00+00:00", "2026-09-01T17:00:00+00:00", 1)],
    )
    assert rows[0].assigned is False
    assert rows[0].reason == "no qualified available substitute"


def test_rejects_duplicate_staff_and_invalid_availability() -> None:
    substitute = SubstituteStaff("same", {"triage"}, "2026-09-01T08:00:00+00:00", "2026-09-01T17:00:00+00:00", 1)
    with pytest.raises(DomainError, match="duplicate substitute"):
        assign_staff_coverage([], [substitute, substitute])
    with pytest.raises(DomainError, match="positive duration"):
        assign_staff_coverage(
            [],
            [SubstituteStaff("bad", {"triage"}, "2026-09-01T17:00:00+00:00", "2026-09-01T08:00:00+00:00", 1)],
        )
