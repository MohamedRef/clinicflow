"""Assess non-clinical appointment document readiness."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class AppointmentDocumentRequirement:
    appointment_id: str
    required_document_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AppointmentDocument:
    appointment_id: str
    document_type: str
    verified: bool
    expired: bool = False


@dataclass(frozen=True, slots=True)
class DocumentReadinessFinding:
    appointment_id: str
    missing_types: tuple[str, ...]
    unverified_types: tuple[str, ...]
    expired_types: tuple[str, ...]
    ready: bool


def assess_document_readiness(
    requirements: list[AppointmentDocumentRequirement], documents: list[AppointmentDocument]
) -> list[DocumentReadinessFinding]:
    """Report missing, unverified, and expired documents by appointment."""
    required: dict[str, tuple[str, ...]] = {}
    for row in requirements:
        appointment_id = clean_code(row.appointment_id, "document appointment id")
        if appointment_id in required:
            raise DomainError(f"duplicate document requirement: {appointment_id}")
        types = tuple(clean_code(item, "required document type").lower() for item in row.required_document_types)
        if not types or len(set(types)) != len(types):
            raise DomainError("required document types must be non-empty and unique")
        required[appointment_id] = types

    received: dict[str, dict[str, AppointmentDocument]] = {}
    for document in documents:
        appointment_id = clean_code(document.appointment_id, "document appointment id")
        if appointment_id not in required:
            raise DomainError(f"document appointment is not configured: {appointment_id}")
        document_type = clean_code(document.document_type, "appointment document type").lower()
        if document_type not in required[appointment_id]:
            raise DomainError(f"unexpected appointment document type: {document_type}")
        appointment_documents = received.setdefault(appointment_id, {})
        if document_type in appointment_documents:
            raise DomainError(f"duplicate appointment document: {appointment_id}/{document_type}")
        appointment_documents[document_type] = document

    findings: list[DocumentReadinessFinding] = []
    for appointment_id, document_types in required.items():
        appointment_documents = received.get(appointment_id, {})
        missing = tuple(sorted(set(document_types) - appointment_documents.keys()))
        unverified = tuple(sorted(key for key, item in appointment_documents.items() if not item.verified))
        expired = tuple(sorted(key for key, item in appointment_documents.items() if item.expired))
        findings.append(
            DocumentReadinessFinding(
                appointment_id=appointment_id,
                missing_types=missing,
                unverified_types=unverified,
                expired_types=expired,
                ready=not missing and not unverified and not expired,
            )
        )
    return sorted(findings, key=lambda item: (item.ready, item.appointment_id))
