import pytest

from clinicflow import (
    DomainError,
    ReceptionFairnessPolicy,
    ReceptionQueueVisit,
    assess_reception_fairness,
)


def test_reception_fairness_reports_waits_and_same_priority_overtakes() -> None:
    visits = [
        ReceptionQueueVisit("early", "c", "2026-09-01T09:00:00Z", "2026-09-01T09:45:00Z"),
        ReceptionQueueVisit("late", "c", "2026-09-01T09:10:00Z", "2026-09-01T09:20:00Z"),
    ]
    findings = assess_reception_fairness(visits, [ReceptionFairnessPolicy("c", 30, 0)])
    early = next(item for item in findings if item.visit_id == "early")
    assert early.wait_minutes == 45
    assert early.overtaken_by == ("late",)
    assert early.excessive_wait


def test_higher_priority_service_is_not_an_unfair_overtake() -> None:
    visits = [
        ReceptionQueueVisit("routine", "c", "2026-09-01T09:00:00Z", "2026-09-01T09:20:00Z", 0),
        ReceptionQueueVisit("priority", "c", "2026-09-01T09:10:00Z", "2026-09-01T09:15:00Z", 1),
    ]
    assert assess_reception_fairness(visits, [ReceptionFairnessPolicy("c", 30, 0)]) == []


def test_reception_fairness_rejects_service_before_arrival() -> None:
    with pytest.raises(DomainError, match="precede"):
        assess_reception_fairness(
            [ReceptionQueueVisit("a", "c", "2026-09-01T10:00:00Z", "2026-09-01T09:00:00Z")],
            [ReceptionFairnessPolicy("c", 30, 0)],
        )
