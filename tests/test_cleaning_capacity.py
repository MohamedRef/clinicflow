import pytest

from clinicflow import CleaningTeam, DomainError, RoomCleaningDemand, allocate_cleaning_capacity


def demand(identifier: str, risk: int, certifications: set[str] | None = None) -> RoomCleaningDemand:
    return RoomCleaningDemand(
        identifier,
        "room-a",
        "2026-09-05T10:00:00+02:00",
        "2026-09-05T12:00:00+02:00",
        45,
        certifications or {"standard"},
        risk,
    )


def team(identifier: str, certifications: set[str]) -> CleaningTeam:
    return CleaningTeam(identifier, certifications, "2026-09-05T08:00:00+02:00", "2026-09-05T18:00:00+02:00", 3)


def test_allocates_high_risk_specialist_work_first() -> None:
    rows = allocate_cleaning_capacity(
        [demand("routine", 2), demand("isolation", 5, {"isolation"})],
        [team("specialist", {"standard", "isolation"}), team("standard", {"standard"})],
    )
    assert [(row.task_id, row.team_id) for row in rows] == [("isolation", "specialist"), ("routine", "standard")]


def test_prevents_team_overlap_and_reports_deadline_shortage() -> None:
    rows = allocate_cleaning_capacity(
        [demand("first", 5), demand("second", 4), demand("third", 3)],
        [CleaningTeam("team", {"standard"}, "2026-09-05T10:00:00+02:00", "2026-09-05T11:00:00+02:00", 3)],
    )
    assert [row.assigned for row in rows] == [True, False, False]


def test_rejects_duplicate_tasks_and_invalid_team_capacity() -> None:
    row = demand("task", 3)
    with pytest.raises(DomainError, match="duplicate cleaning task"):
        allocate_cleaning_capacity([row, row], [])
    with pytest.raises(DomainError, match="maximum_tasks"):
        allocate_cleaning_capacity(
            [], [CleaningTeam("team", set(), "2026-09-05T08:00:00+02:00", "2026-09-05T18:00:00+02:00", 0)]
        )
