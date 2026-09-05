"""Deterministic room cleaning evidence assessment."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum


class RoomCleaningEvidenceDisposition(StrEnum):
    READY = "ready"
    ATTENTION = "attention"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class RoomCleaningEvidenceObservation:
    observation_id: str
    owner: str
    due_minute: int
    completed_minute: int | None
    required_signals: tuple[str, ...]
    observed_signals: tuple[str, ...]
    exposure_units: int


@dataclass(frozen=True, slots=True)
class RoomCleaningEvidenceFinding:
    observation_id: str
    owner: str
    disposition: RoomCleaningEvidenceDisposition
    missing_signals: tuple[str, ...]
    overdue_minutes: int
    exposure_units: int


def _required_text(value: str, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"room cleaning evidence {field} is required")
    return normalized


def _normalized_signals(values: Sequence[str], field: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        normalized = _required_text(value, field)
        key = normalized.casefold()
        if key in result:
            raise ValueError(f"duplicate room cleaning evidence {field}: {normalized}")
        result[key] = normalized
    return result


def assess_room_cleaning_evidence(
    observations: Iterable[RoomCleaningEvidenceObservation],
    review_minute: int,
) -> tuple[RoomCleaningEvidenceFinding, ...]:
    """Return blockers first, then attention and ready observations."""
    if review_minute <= 0:
        raise ValueError("room cleaning evidence review minute must be positive")

    seen: set[str] = set()
    findings: list[RoomCleaningEvidenceFinding] = []
    for observation in observations:
        observation_id = _required_text(observation.observation_id, "id")
        identity = observation_id.casefold()
        if identity in seen:
            raise ValueError(f"duplicate room cleaning evidence observation: {observation_id}")
        seen.add(identity)
        owner = _required_text(observation.owner, "owner")
        if observation.due_minute <= 0:
            raise ValueError("room cleaning evidence due minute must be positive")
        if observation.completed_minute is not None and not (0 < observation.completed_minute <= review_minute):
            raise ValueError("room cleaning evidence completion minute is invalid")
        if observation.exposure_units < 0:
            raise ValueError("room cleaning evidence exposure must be non-negative")

        required = _normalized_signals(observation.required_signals, "required signal")
        observed = _normalized_signals(observation.observed_signals, "observed signal")
        missing = tuple(
            sorted(
                (display for key, display in required.items() if key not in observed),
                key=str.casefold,
            )
        )
        effective_minute = observation.completed_minute or review_minute
        overdue = max(0, effective_minute - observation.due_minute)
        if missing and observation.due_minute <= review_minute:
            disposition = RoomCleaningEvidenceDisposition.BLOCKED
        elif missing or overdue:
            disposition = RoomCleaningEvidenceDisposition.ATTENTION
        else:
            disposition = RoomCleaningEvidenceDisposition.READY
        findings.append(
            RoomCleaningEvidenceFinding(
                observation_id=observation_id,
                owner=owner,
                disposition=disposition,
                missing_signals=missing,
                overdue_minutes=overdue,
                exposure_units=observation.exposure_units,
            )
        )

    priority = {
        RoomCleaningEvidenceDisposition.BLOCKED: 0,
        RoomCleaningEvidenceDisposition.ATTENTION: 1,
        RoomCleaningEvidenceDisposition.READY: 2,
    }
    return tuple(
        sorted(
            findings,
            key=lambda item: (
                priority[item.disposition],
                -item.exposure_units,
                -item.overdue_minutes,
                item.observation_id,
            ),
        )
    )
