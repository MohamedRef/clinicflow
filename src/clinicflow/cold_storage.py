"""Temperature-excursion review for clinic inventory storage."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .models import DomainError, clean_code, parse_time


class ColdStorageDisposition(StrEnum):
    STABLE = "stable"
    AT_RISK = "at-risk"
    EXCURSION = "excursion"
    MISSING_BASELINE = "missing-baseline"


@dataclass(frozen=True, slots=True)
class StorageTemperatureReading:
    storage_id: str
    observed_at: str
    celsius: float


@dataclass(frozen=True, slots=True)
class TemperatureControlledBatch:
    batch_id: str
    sku: str
    storage_id: str
    monitored_from_at: str
    minimum_celsius: float
    maximum_celsius: float
    maximum_excursion_minutes: int


@dataclass(frozen=True, slots=True)
class ColdStorageAssessment:
    batch_id: str
    disposition: ColdStorageDisposition
    excursion_minutes: int
    first_excursion_at: str | None
    last_reading_at: str | None


def assess_cold_storage(
    batches: list[TemperatureControlledBatch],
    readings: list[StorageTemperatureReading],
    assessed_at: str,
) -> list[ColdStorageAssessment]:
    """Measure sustained out-of-range periods using the last observed state."""
    now = parse_time(assessed_at, "assessed_at")
    streams: dict[str, list[tuple[datetime, float]]] = {}
    reading_keys: set[tuple[str, datetime]] = set()
    for reading in readings:
        storage_id = clean_code(reading.storage_id, "storage id")
        observed_at = parse_time(reading.observed_at, "observed_at")
        if observed_at > now:
            raise DomainError("temperature reading cannot follow assessed_at")
        temperature = _finite_number(reading.celsius, "reading celsius")
        key = (storage_id, observed_at)
        if key in reading_keys:
            raise DomainError(f"duplicate temperature reading: {storage_id} at {observed_at.isoformat()}")
        reading_keys.add(key)
        streams.setdefault(storage_id, []).append((observed_at, temperature))
    for stream in streams.values():
        stream.sort()

    seen_batches: set[str] = set()
    assessments: list[ColdStorageAssessment] = []
    for batch in batches:
        batch_id = clean_code(batch.batch_id, "batch id")
        if batch_id in seen_batches:
            raise DomainError(f"duplicate temperature-controlled batch id: {batch_id}")
        seen_batches.add(batch_id)
        clean_code(batch.sku, "sku")
        storage_id = clean_code(batch.storage_id, "storage id")
        monitored_from = parse_time(batch.monitored_from_at, "monitored_from_at")
        if monitored_from > now:
            raise DomainError("monitored_from_at cannot follow assessed_at")
        minimum = _finite_number(batch.minimum_celsius, "minimum celsius")
        maximum = _finite_number(batch.maximum_celsius, "maximum celsius")
        if maximum <= minimum:
            raise DomainError("maximum celsius must exceed minimum celsius")
        if (
            isinstance(batch.maximum_excursion_minutes, bool)
            or not isinstance(batch.maximum_excursion_minutes, int)
            or not 0 <= batch.maximum_excursion_minutes <= 1440
        ):
            raise DomainError("maximum excursion minutes must be from 0 through 1440")

        stream = streams.get(storage_id, [])
        baseline_index = next(
            (index for index in range(len(stream) - 1, -1, -1) if stream[index][0] <= monitored_from),
            None,
        )
        if baseline_index is None:
            assessments.append(
                ColdStorageAssessment(
                    batch_id,
                    ColdStorageDisposition.MISSING_BASELINE,
                    0,
                    None,
                    stream[-1][0].isoformat() if stream else None,
                )
            )
            continue

        relevant = [(monitored_from, stream[baseline_index][1]), *stream[baseline_index + 1 :]]
        excursion_seconds = 0.0
        first_excursion: datetime | None = None
        for index, (observed_at, temperature) in enumerate(relevant):
            interval_end = relevant[index + 1][0] if index + 1 < len(relevant) else now
            if minimum <= temperature <= maximum:
                continue
            if first_excursion is None:
                first_excursion = observed_at
            excursion_seconds += (interval_end - observed_at).total_seconds()
        excursion_minutes = math.ceil(excursion_seconds / 60)
        if excursion_minutes == 0:
            disposition = ColdStorageDisposition.STABLE
        elif excursion_minutes > batch.maximum_excursion_minutes:
            disposition = ColdStorageDisposition.EXCURSION
        else:
            disposition = ColdStorageDisposition.AT_RISK
        assessments.append(
            ColdStorageAssessment(
                batch_id,
                disposition,
                excursion_minutes,
                first_excursion.isoformat() if first_excursion else None,
                stream[-1][0].isoformat(),
            )
        )
    return sorted(assessments, key=lambda assessment: assessment.batch_id)


def _finite_number(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DomainError(f"{field_name} must be a finite number")
    return float(value)
