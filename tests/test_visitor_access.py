from dataclasses import replace

import pytest

from clinicflow import AccessDeskWindow, DomainError, VisitorAccessRequest, schedule_visitor_access


def request(identifier: str = "visit-a") -> VisitorAccessRequest:
    return VisitorAccessRequest(
        identifier,
        "Vendor Engineer",
        "Facilities",
        "2026-09-02T10:00:00+02:00",
        "2026-09-02T12:00:00+02:00",
        ("plant-room",),
        "2026-09-03T00:00:00+02:00",
        "2026-08-01T08:00:00+02:00",
    )


def window(identifier: str = "desk-a") -> AccessDeskWindow:
    return AccessDeskWindow(
        identifier, "2026-09-02T08:00:00+02:00", "2026-09-02T11:00:00+02:00", ("plant-room", "stores"), 1
    )


def test_schedules_valid_credential_issue_and_honors_capacity() -> None:
    rows = schedule_visitor_access([request("a"), request("b")], [window()], "2026-09-01T08:00:00+02:00")
    assert rows[0].assigned is True
    assert rows[1].assigned is False


def test_reports_expiring_credentials_and_stale_training() -> None:
    expiring = replace(request("expiring"), credential_expires_at="2026-09-02T11:00:00+02:00")
    stale = replace(request("stale"), safety_trained_at="2024-01-01T00:00:00+02:00")
    rows = schedule_visitor_access([expiring, stale], [window()], "2026-09-01T08:00:00+02:00")
    assert {row.reason for row in rows} == {"credential expires before visit ends", "safety training is stale"}


def test_rejects_duplicate_windows_and_requested_zones() -> None:
    with pytest.raises(DomainError, match="duplicate access window"):
        schedule_visitor_access([], [window("Desk-A"), window("desk-a")], "2026-09-01T08:00:00+02:00")
    with pytest.raises(DomainError, match="non-empty and unique"):
        schedule_visitor_access(
            [replace(request(), zones=("Plant-Room", "plant-room"))], [window()], "2026-09-01T08:00:00+02:00"
        )
