import pytest

from clinicflow import DomainError, RepairCrew, RoomDowntime, plan_room_downtime_repairs


def incident(identifier: str, impact: int, skills: set[str] | None = None) -> RoomDowntime:
    return RoomDowntime(
        identifier,
        "room-a",
        "2026-08-28T08:00:00+03:00",
        "2026-08-28T12:00:00+03:00",
        90,
        skills or {"electrical"},
        impact,
    )


def test_prioritizes_high_impact_repairs_and_preserves_crew_capacity() -> None:
    crew = RepairCrew("crew-a", {"electrical"}, "2026-08-28T08:00:00+03:00", "2026-08-28T11:00:00+03:00", 2)
    rows = plan_room_downtime_repairs(
        [incident("routine", 1), incident("critical", 8), incident("overflow", 2)], [crew]
    )
    assert [(row.incident_id, row.crew_id) for row in rows] == [
        ("critical", "crew-a"),
        ("overflow", "crew-a"),
        ("routine", None),
    ]
    assert rows[0].on_time and rows[1].on_time


def test_rejects_duplicate_incidents_and_invalid_crew_limits() -> None:
    row = incident("same", 1)
    with pytest.raises(DomainError, match="duplicate downtime incident"):
        plan_room_downtime_repairs([row, row], [])
    with pytest.raises(DomainError, match="maximum_jobs"):
        plan_room_downtime_repairs(
            [], [RepairCrew("crew", set(), "2026-08-28T08:00:00+03:00", "2026-08-28T10:00:00+03:00", 0)]
        )
