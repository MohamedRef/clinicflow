from datetime import UTC, datetime, timedelta

import pytest

from clinicflow import DocumentCourierDemand, DocumentCourierShift, schedule_document_couriers
from clinicflow.models import DomainError


def test_schedules_urgent_sealed_package_and_blocks_untracked_package() -> None:
    now = datetime(2026, 9, 4, 9, tzinfo=UTC)
    rows = schedule_document_couriers(
        [
            DocumentCourierDemand("urgent", "main", now, now + timedelta(hours=2), True, True),
            DocumentCourierDemand("untracked", "main", now, now + timedelta(hours=3), True, False),
        ],
        [DocumentCourierShift("courier", ("MAIN",), now + timedelta(hours=1), 1)],
    )
    assert rows[0].assigned and rows[0].shift_id == "courier"
    assert rows[1].reason == "tracking_not_registered"


def test_rejects_inverted_demand_window_and_duplicate_shift() -> None:
    now = datetime(2026, 9, 4, tzinfo=UTC)
    with pytest.raises(DomainError, match="demand"):
        schedule_document_couriers(
            [DocumentCourierDemand("package", "main", now, now - timedelta(seconds=1), True, True)], []
        )
    shift = DocumentCourierShift("shift", ("main",), now, 1)
    with pytest.raises(DomainError, match="shift"):
        schedule_document_couriers([], [shift, DocumentCourierShift("SHIFT", ("main",), now, 1)])
