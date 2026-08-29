"""Public behavior tests for clinic staff break coverage."""

import pytest

from clinicflow import BreakRequest, ReliefStaff, schedule_break_coverage
from clinicflow.models import DomainError


def request(identifier: str, priority: int, qualifications: set[str] | None = None) -> BreakRequest:
    return BreakRequest(
        identifier,
        f"owner-{identifier}",
        "2026-09-01T10:00:00+00:00",
        "2026-09-01T11:00:00+00:00",
        30,
        qualifications or {"front-desk"},
        priority,
    )


def relief(identifier: str, qualifications: set[str], maximum_breaks: int = 2) -> ReliefStaff:
    return ReliefStaff(
        identifier,
        qualifications,
        "2026-09-01T09:00:00+00:00",
        "2026-09-01T12:00:00+00:00",
        maximum_breaks,
    )


def test_schedules_priority_breaks_without_relief_overlap() -> None:
    rows = schedule_break_coverage(
        [request("routine", 1), request("urgent", 5), request("middle", 3)],
        [relief("relief-a", {"front-desk"}), relief("relief-b", {"front-desk"}, 1)],
    )
    assert [(row.break_id, row.relief_staff_id, row.starts_at) for row in rows] == [
        ("urgent", "relief-a", "2026-09-01T10:00:00+00:00"),
        ("middle", "relief-b", "2026-09-01T10:00:00+00:00"),
        ("routine", "relief-a", "2026-09-01T10:30:00+00:00"),
    ]


def test_reports_uncovered_break_without_losing_other_assignments() -> None:
    rows = schedule_break_coverage(
        [request("specialist", 5, {"inventory"}), request("desk", 2)],
        [relief("relief", {"front-desk"}, 1)],
    )
    assert rows[0].assigned is False
    assert rows[0].reason == "no qualified relief window"
    assert rows[1].assigned is True


def test_rejects_duplicate_relief_and_breaks_that_do_not_fit() -> None:
    member = relief("same", {"front-desk"})
    with pytest.raises(DomainError, match="duplicate relief"):
        schedule_break_coverage([], [member, member])
    invalid = BreakRequest(
        "bad",
        "staff",
        "2026-09-01T10:00:00+00:00",
        "2026-09-01T10:20:00+00:00",
        30,
        set(),
        1,
    )
    with pytest.raises(DomainError, match="does not fit"):
        schedule_break_coverage([invalid], [])
