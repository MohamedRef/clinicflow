from datetime import UTC, datetime, timedelta

import pytest

from clinicflow import SanitationTeamWindow, WaitingRoomSanitationNeed, schedule_waiting_room_sanitation
from clinicflow.models import DomainError


def test_assigns_most_overdue_waiting_zone_first() -> None:
    now = datetime(2026, 9, 4, 10, tzinfo=UTC)
    result = schedule_waiting_room_sanitation(
        [
            WaitingRoomSanitationNeed("recent", now - timedelta(minutes=30), 60, 20),
            WaitingRoomSanitationNeed("overdue", now - timedelta(hours=3), 60, 1),
        ],
        [SanitationTeamWindow("team", now, 1)],
        as_of=now,
    )
    assert result[0].zone_id == "overdue" and result[0].assigned
    assert not result[1].assigned


def test_rejects_future_cleaning_record() -> None:
    now = datetime(2026, 9, 4, 10, tzinfo=UTC)
    with pytest.raises(DomainError, match="future"):
        schedule_waiting_room_sanitation(
            [WaitingRoomSanitationNeed("zone", now + timedelta(minutes=1), 60, 0)], [], as_of=now
        )
