from dataclasses import replace

import pytest

from clinicflow import ConfirmationCase, ConfirmationStatus, DomainError, review_confirmations


def case(identifier: str) -> ConfirmationCase:
    return ConfirmationCase(
        identifier,
        "2026-09-01T12:00:00+02:00",
        "2026-08-31T12:00:00+02:00",
        True,
        1,
        3,
    )


def test_prioritizes_exhausted_and_overdue_confirmations() -> None:
    exhausted = replace(case("exhausted"), contact_attempts=3)
    overdue = case("overdue")
    pending = replace(case("pending"), confirmation_due_at="2026-08-31T18:00:00+02:00")
    rows = review_confirmations([pending, overdue, exhausted], "2026-08-31T15:00:00+02:00")
    assert [row.appointment_id for row in rows] == ["exhausted", "overdue", "pending"]
    assert rows[0].status is ConfirmationStatus.CONTACT_EXHAUSTED
    assert rows[1].minutes_overdue == 180
    assert rows[1].next_action == "contact_now"


def test_confirmed_case_requires_no_follow_up() -> None:
    confirmed = replace(case("confirmed"), confirmed_at="2026-08-30T12:00:00+02:00")
    [row] = review_confirmations([confirmed], "2026-08-31T15:00:00+02:00")
    assert row.status is ConfirmationStatus.CONFIRMED
    assert row.minutes_overdue == 0
    assert row.next_action == "none"


def test_rejects_casefold_duplicates_and_invalid_histories() -> None:
    with pytest.raises(DomainError, match="duplicate confirmation"):
        review_confirmations([case("Visit-A"), case("visit-a")], "2026-08-31T15:00:00+02:00")
    with pytest.raises(DomainError, match="before appointment"):
        review_confirmations(
            [replace(case("visit"), confirmation_due_at="2026-09-01T13:00:00+02:00")],
            "2026-08-31T15:00:00+02:00",
        )
    with pytest.raises(DomainError, match="cannot exceed"):
        review_confirmations(
            [replace(case("visit"), contact_attempts=4)],
            "2026-08-31T15:00:00+02:00",
        )
