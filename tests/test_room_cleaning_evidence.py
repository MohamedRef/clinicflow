import pytest

from clinicflow.room_cleaning_evidence import (
    RoomCleaningEvidenceDisposition,
    RoomCleaningEvidenceObservation,
    assess_room_cleaning_evidence,
)


def _observation(**overrides: object) -> RoomCleaningEvidenceObservation:
    values: dict[str, object] = {
        "observation_id": "case-1",
        "owner": "operations",
        "due_minute": 80,
        "completed_minute": None,
        "required_signals": ("approval",),
        "observed_signals": ("approval",),
        "exposure_units": 10,
    }
    values.update(overrides)
    return RoomCleaningEvidenceObservation(**values)  # type: ignore[arg-type]


def test_room_cleaning_evidence_orders_blocked_evidence() -> None:
    findings = assess_room_cleaning_evidence(
        [
            _observation(
                observation_id="ready-1",
                due_minute=100,
                completed_minute=90,
                exposure_units=20,
            ),
            _observation(
                observation_id="blocked-1",
                required_signals=("approval", "receipt"),
                observed_signals=("approval",),
                exposure_units=90,
            ),
        ],
        100,
    )

    assert [finding.observation_id for finding in findings] == ["blocked-1", "ready-1"]
    assert findings[0].disposition is RoomCleaningEvidenceDisposition.BLOCKED
    assert findings[0].missing_signals == ("receipt",)
    assert findings[0].overdue_minutes == 20


def test_room_cleaning_evidence_separates_future_and_late_attention() -> None:
    findings = assess_room_cleaning_evidence(
        [
            _observation(
                observation_id="future-gap",
                due_minute=120,
                required_signals=("handoff",),
                observed_signals=(),
            ),
            _observation(
                observation_id="late-complete",
                due_minute=60,
                completed_minute=90,
                required_signals=("handoff",),
                observed_signals=("handoff",),
                exposure_units=20,
            ),
        ],
        100,
    )

    assert findings[0].observation_id == "late-complete"
    assert findings[0].overdue_minutes == 30
    assert findings[1].disposition is RoomCleaningEvidenceDisposition.ATTENTION
    assert findings[1].overdue_minutes == 0


def test_room_cleaning_evidence_rejects_ambiguous_evidence() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        assess_room_cleaning_evidence(
            [
                _observation(observation_id="same"),
                _observation(observation_id=" SAME "),
            ],
            100,
        )
    with pytest.raises(ValueError, match="duplicate"):
        assess_room_cleaning_evidence(
            [_observation(observed_signals=("receipt", " RECEIPT "))],
            100,
        )
    with pytest.raises(ValueError, match="non-negative"):
        assess_room_cleaning_evidence([_observation(exposure_units=-1)], 100)
