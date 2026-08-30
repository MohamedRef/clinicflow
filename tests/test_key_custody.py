import pytest

from clinicflow import DomainError, KeyCustodyEvent, KeyCustodyEventType, reconcile_key_custody


def event(
    identifier: str, key_id: str, kind: KeyCustodyEventType, custodian: str, occurred_at: str, due_at: str | None = None
) -> KeyCustodyEvent:
    return KeyCustodyEvent(identifier, key_id, kind, custodian, occurred_at, due_at)


def test_reconciles_returned_and_overdue_clinic_keys() -> None:
    positions = reconcile_key_custody(
        [
            event("1", "pharmacy", KeyCustodyEventType.ISSUED, "Sam", "2026-08-30T08:00:00Z", "2026-08-30T10:00:00Z"),
            event("2", "store", KeyCustodyEventType.ISSUED, "Lee", "2026-08-30T08:00:00Z", "2026-08-30T09:00:00Z"),
            event("3", "pharmacy", KeyCustodyEventType.RETURNED, "Sam", "2026-08-30T09:00:00Z"),
        ],
        "2026-08-30T09:30:00Z",
    )
    assert positions[0].custodian is None
    assert positions[1].custodian == "Lee"
    assert positions[1].overdue is True


def test_rejects_double_issue_and_wrong_return_custodian() -> None:
    issue = event("1", "store", KeyCustodyEventType.ISSUED, "Sam", "2026-08-30T08:00:00Z", "2026-08-30T10:00:00Z")
    with pytest.raises(DomainError, match="already issued"):
        reconcile_key_custody(
            [
                issue,
                event("2", "store", KeyCustodyEventType.ISSUED, "Lee", "2026-08-30T09:00:00Z", "2026-08-30T11:00:00Z"),
            ],
            "2026-08-30T12:00:00Z",
        )
    with pytest.raises(DomainError, match="does not match"):
        reconcile_key_custody(
            [issue, event("2", "store", KeyCustodyEventType.RETURNED, "Lee", "2026-08-30T09:00:00Z")],
            "2026-08-30T12:00:00Z",
        )
