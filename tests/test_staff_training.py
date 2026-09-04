import pytest

from clinicflow import DomainError, StaffDutyRequirement, StaffTrainingRecord, assess_staff_training


def test_staff_training_is_assessed_at_duty_start() -> None:
    records = [StaffTrainingRecord("staff", "fire marshal", "2026-01-01T00:00:00Z", "2026-09-01T00:00:00Z")]
    rows = assess_staff_training(
        records,
        [
            StaffDutyRequirement("late", "staff", "fire marshal", "2026-09-02T00:00:00Z"),
            StaffDutyRequirement("missing", "staff", "spill response", "2026-08-01T00:00:00Z"),
        ],
    )
    assert [row.reason for row in rows] == ["training expired", "required training is missing"]


def test_staff_training_rejects_case_aliased_evidence() -> None:
    rows = [
        StaffTrainingRecord("Staff", "Fire", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z"),
        StaffTrainingRecord("staff", "fire", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z"),
    ]
    with pytest.raises(DomainError, match="duplicate"):
        assess_staff_training(rows, [])
