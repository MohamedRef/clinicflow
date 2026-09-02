import pytest

from clinicflow import DomainError, StaffAreaAssignment, StaffBadgeGrant, assess_staff_badges


def test_staff_badges_separate_missing_expired_and_suspended_areas() -> None:
    assignments = [
        StaffAreaAssignment("staff", "reception"),
        StaffAreaAssignment("staff", "store"),
        StaffAreaAssignment("staff", "records"),
    ]
    grants = [
        StaffBadgeGrant("staff", "reception", 9),
        StaffBadgeGrant("staff", "store", 20, True),
    ]
    [finding] = assess_staff_badges(assignments, grants, 10)
    assert finding.expired_area_ids == ("reception",)
    assert finding.suspended_area_ids == ("store",)
    assert finding.missing_area_ids == ("records",)
    assert not finding.ready


def test_staff_badges_reject_unassigned_grants() -> None:
    with pytest.raises(DomainError, match="match an assignment"):
        assess_staff_badges(
            [StaffAreaAssignment("staff", "reception")],
            [StaffBadgeGrant("staff", "store", 20)],
            10,
        )
