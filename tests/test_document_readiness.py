import pytest

from clinicflow import (
    AppointmentDocument,
    AppointmentDocumentRequirement,
    DomainError,
    assess_document_readiness,
)


def test_document_readiness_reports_each_kind_of_gap() -> None:
    findings = assess_document_readiness(
        [AppointmentDocumentRequirement("a-1", ("consent", "coverage", "referral"))],
        [
            AppointmentDocument("a-1", "consent", verified=False),
            AppointmentDocument("a-1", "coverage", verified=True, expired=True),
        ],
    )
    assert findings[0].missing_types == ("referral",)
    assert findings[0].unverified_types == ("consent",)
    assert findings[0].expired_types == ("coverage",)
    assert not findings[0].ready


def test_document_readiness_accepts_a_complete_verified_set() -> None:
    findings = assess_document_readiness(
        [AppointmentDocumentRequirement("a", ("consent",))],
        [AppointmentDocument("a", "consent", verified=True)],
    )
    assert findings[0].ready


def test_document_readiness_rejects_unexpected_document_types() -> None:
    with pytest.raises(DomainError, match="unexpected"):
        assess_document_readiness(
            [AppointmentDocumentRequirement("a", ("consent",))],
            [AppointmentDocument("a", "other", verified=True)],
        )
