"""Public behavior tests for appointment accessibility readiness."""

import pytest

from clinicflow import (
    AccessibilityDisposition,
    AppointmentAccessibilityNeed,
    RoomAccessibilityCheck,
    assess_accessibility_readiness,
)
from clinicflow.models import DomainError


def need(identifier: str, room_id: str, features: set[str]) -> AppointmentAccessibilityNeed:
    return AppointmentAccessibilityNeed(
        identifier,
        room_id,
        "2026-09-01T10:00:00+00:00",
        features,
    )


def check(
    room_id: str,
    checked_at: str,
    valid_until: str,
    available: set[str],
    unavailable: set[str] | None = None,
) -> RoomAccessibilityCheck:
    return RoomAccessibilityCheck(room_id, checked_at, valid_until, available, unavailable or set())


def test_uses_latest_valid_room_check_and_reports_missing_features() -> None:
    rows = assess_accessibility_readiness(
        [
            need("ready", "room-a", {"step-free", "hearing-loop"}),
            need("missing", "room-b", {"step-free", "hearing-loop"}),
        ],
        [
            check(
                "room-a",
                "2026-09-01T08:00:00+00:00",
                "2026-09-01T12:00:00+00:00",
                {"step-free"},
            ),
            check(
                "room-a",
                "2026-09-01T09:00:00+00:00",
                "2026-09-01T11:00:00+00:00",
                {"step-free", "hearing-loop"},
            ),
            check(
                "room-b",
                "2026-09-01T09:00:00+00:00",
                "2026-09-01T11:00:00+00:00",
                {"step-free"},
                {"hearing-loop"},
            ),
        ],
    )
    assert rows[0].disposition is AccessibilityDisposition.MISSING_FEATURES
    assert rows[0].missing_features == ("hearing-loop",)
    assert rows[1].disposition is AccessibilityDisposition.READY
    assert rows[1].evidence_checked_at == "2026-09-01T09:00:00+00:00"


def test_distinguishes_stale_checks_from_unassessed_rooms() -> None:
    rows = assess_accessibility_readiness(
        [need("stale", "room-a", {"step-free"}), need("unknown", "room-b", {"step-free"})],
        [
            check(
                "room-a",
                "2026-09-01T07:00:00+00:00",
                "2026-09-01T09:00:00+00:00",
                {"step-free"},
            )
        ],
    )
    assert rows[0].disposition is AccessibilityDisposition.STALE_CHECK
    assert rows[1].disposition is AccessibilityDisposition.UNASSESSED
    assert rows[1].evidence_checked_at is None


def test_rejects_conflicting_features_and_duplicate_appointment_needs() -> None:
    conflicting = check(
        "room-a",
        "2026-09-01T08:00:00+00:00",
        "2026-09-01T11:00:00+00:00",
        {"step-free"},
        {"step-free"},
    )
    with pytest.raises(DomainError, match="both available and unavailable"):
        assess_accessibility_readiness([], [conflicting])
    repeated = need("same", "room-a", {"step-free"})
    with pytest.raises(DomainError, match="duplicate accessibility appointment"):
        assess_accessibility_readiness([repeated, repeated], [])
