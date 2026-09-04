from datetime import UTC, datetime

import pytest

from clinicflow import MobilityEquipmentCheck, assess_mobility_equipment
from clinicflow.models import DomainError


def test_prioritizes_unsafe_and_stale_mobility_equipment() -> None:
    reviewed_at = datetime(2026, 9, 4, tzinfo=UTC)
    rows = assess_mobility_equipment(
        [
            MobilityEquipmentCheck("ready", "wheelchair", reviewed_at, True, True, True),
            MobilityEquipmentCheck("reserved", "wheelchair", reviewed_at, True, True, True, "appointment"),
            MobilityEquipmentCheck("dirty", "wheelchair", reviewed_at, True, True, False),
            MobilityEquipmentCheck("unsafe", "wheelchair", reviewed_at, False, True, True),
        ],
        reviewed_at=reviewed_at,
    )
    assert [row.state for row in rows] == ["quarantine", "refresh", "reserved", "ready"]
    assert rows[0].defects == ("brake_fault",)


def test_rejects_duplicate_and_future_mobility_checks() -> None:
    reviewed_at = datetime(2026, 9, 4, tzinfo=UTC)
    valid = MobilityEquipmentCheck("chair", "wheelchair", reviewed_at, True, True, True)
    with pytest.raises(DomainError, match="duplicate"):
        assess_mobility_equipment(
            [valid, MobilityEquipmentCheck(" CHAIR ", "wheelchair", reviewed_at, True, True, True)],
            reviewed_at=reviewed_at,
        )
    with pytest.raises(DomainError, match="future"):
        assess_mobility_equipment(
            [MobilityEquipmentCheck("chair", "wheelchair", datetime(2026, 9, 5, tzinfo=UTC), True, True, True)],
            reviewed_at=reviewed_at,
        )
    with pytest.raises(DomainError, match="timezone-aware"):
        assess_mobility_equipment([valid], reviewed_at=datetime(2026, 9, 4))
