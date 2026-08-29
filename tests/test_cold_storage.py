"""Public behavior tests for cold-storage excursion review."""

import pytest

from clinicflow import (
    ColdStorageDisposition,
    StorageTemperatureReading,
    TemperatureControlledBatch,
    assess_cold_storage,
)
from clinicflow.models import DomainError


def batch(identifier: str, storage_id: str = "cold-a", allowance: int = 30) -> TemperatureControlledBatch:
    return TemperatureControlledBatch(
        identifier,
        "supply-1",
        storage_id,
        "2026-09-01T08:00:00+00:00",
        2.0,
        8.0,
        allowance,
    )


def reading(storage_id: str, observed_at: str, celsius: float) -> StorageTemperatureReading:
    return StorageTemperatureReading(storage_id, observed_at, celsius)


def test_measures_stable_at_risk_and_excursion_periods() -> None:
    readings = [
        reading("cold-a", "2026-09-01T07:55:00+00:00", 5.0),
        reading("cold-a", "2026-09-01T08:30:00+00:00", 9.0),
        reading("cold-a", "2026-09-01T08:50:00+00:00", 5.0),
        reading("cold-b", "2026-09-01T07:55:00+00:00", 5.0),
        reading("cold-b", "2026-09-01T08:10:00+00:00", 9.0),
        reading("cold-c", "2026-09-01T07:55:00+00:00", 5.0),
    ]
    rows = assess_cold_storage(
        [batch("stable", "cold-c"), batch("at-risk", allowance=30), batch("excursion", "cold-b", 20)],
        readings,
        "2026-09-01T08:55:00+00:00",
    )
    assert rows[0].disposition is ColdStorageDisposition.AT_RISK
    assert rows[0].excursion_minutes == 20
    assert rows[1].disposition is ColdStorageDisposition.EXCURSION
    assert rows[1].excursion_minutes == 45
    assert rows[2].disposition is ColdStorageDisposition.STABLE


def test_reports_missing_baseline_without_inventing_safe_coverage() -> None:
    rows = assess_cold_storage(
        [batch("unverified")],
        [reading("cold-a", "2026-09-01T08:05:00+00:00", 5.0)],
        "2026-09-01T08:10:00+00:00",
    )
    assert rows[0].disposition is ColdStorageDisposition.MISSING_BASELINE
    assert rows[0].last_reading_at == "2026-09-01T08:05:00+00:00"


def test_rejects_duplicate_readings_and_invalid_temperature_controls() -> None:
    duplicate = reading("cold-a", "2026-09-01T08:00:00+00:00", 5.0)
    with pytest.raises(DomainError, match="duplicate temperature"):
        assess_cold_storage([], [duplicate, duplicate], "2026-09-01T09:00:00+00:00")
    invalid = TemperatureControlledBatch(
        "bad",
        "sku",
        "cold-a",
        "2026-09-01T08:00:00+00:00",
        8.0,
        2.0,
        10,
    )
    with pytest.raises(DomainError, match="must exceed"):
        assess_cold_storage([invalid], [], "2026-09-01T09:00:00+00:00")
