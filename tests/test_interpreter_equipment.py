from datetime import UTC, datetime, timedelta

import pytest

from clinicflow import InterpreterEquipmentDemand, InterpreterEquipmentUnit, allocate_interpreter_equipment
from clinicflow.models import DomainError


def test_reserves_video_unit_for_video_demand() -> None:
    start = datetime(2026, 9, 4, 10, tzinfo=UTC)
    result = allocate_interpreter_equipment(
        [
            InterpreterEquipmentDemand("video", "arabic", start, needs_video=True),
            InterpreterEquipmentDemand("audio", "arabic", start),
        ],
        [
            InterpreterEquipmentUnit("audio", ("arabic",), False, start - timedelta(hours=1)),
            InterpreterEquipmentUnit("video", ("arabic",), True, start - timedelta(hours=1)),
        ],
    )
    assert result[0].appointment_id == "video" and result[0].unit_id == "video"
    assert result[1].unit_id == "audio"


def test_rejects_naive_availability() -> None:
    with pytest.raises(DomainError, match="timezone-aware"):
        allocate_interpreter_equipment([], [InterpreterEquipmentUnit("unit", ("arabic",), True, datetime(2026, 9, 4))])
