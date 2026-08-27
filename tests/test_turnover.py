import pytest

from clinicflow import RoomUse, plan_room_turnover
from clinicflow.models import DomainError


def use(identifier: str, room: str, procedure: str, starts: str, ends: str) -> RoomUse:
    return RoomUse(identifier, room, procedure, starts, ends)


def test_plans_turnover_and_exposes_shortfalls_per_room() -> None:
    tasks = plan_room_turnover(
        [
            use("a", "room-1", "imaging", "2026-09-01T09:00:00+00:00", "2026-09-01T10:00:00+00:00"),
            use("b", "room-1", "consult", "2026-09-01T10:20:00+00:00", "2026-09-01T11:00:00+00:00"),
            use("c", "room-1", "consult", "2026-09-01T11:05:00+00:00", "2026-09-01T12:00:00+00:00"),
        ],
        {"imaging": 30, "consult": 10},
    )
    assert tasks[0].available_minutes == 20
    assert tasks[0].shortfall_minutes == 10
    assert tasks[1].available_minutes == 5
    assert tasks[1].shortfall_minutes == 5


def test_uses_default_reset_and_reports_overlapping_appointments() -> None:
    tasks = plan_room_turnover(
        [
            use("a", "room-1", "unknown", "2026-09-01T09:00:00+00:00", "2026-09-01T10:00:00+00:00"),
            use("b", "room-1", "consult", "2026-09-01T09:50:00+00:00", "2026-09-01T11:00:00+00:00"),
        ],
        {},
    )
    assert tasks[0].required_minutes == 15
    assert tasks[0].available_minutes == 0
    assert tasks[0].shortfall_minutes == 25


@pytest.mark.parametrize(
    "uses,rules,message",
    [
        (
            [
                use("same", "r1", "a", "2026-09-01T09:00:00+00:00", "2026-09-01T10:00:00+00:00"),
                use("same", "r2", "b", "2026-09-01T10:00:00+00:00", "2026-09-01T11:00:00+00:00"),
            ],
            {},
            "duplicate appointment",
        ),
        ([], {"consult": -1}, "turnover minutes"),
    ],
)
def test_invalid_turnover_inputs_fail_closed(uses: list[RoomUse], rules: dict[str, int], message: str) -> None:
    with pytest.raises(DomainError, match=message):
        plan_room_turnover(uses, rules)
