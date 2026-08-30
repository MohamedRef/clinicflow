"""Clinic opening checklist readiness for rooms, staffing, supplies, and facilities."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from .models import DomainError, clean_code, clean_text, parse_time


class OpeningCheckStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    WAIVED = "waived"


@dataclass(frozen=True, slots=True)
class OpeningCheck:
    check_id: str
    category: str
    owner: str
    due_at: str
    status: OpeningCheckStatus
    completed_at: str | None
    completed_by: str | None
    evidence: str | None
    waiver_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ClinicOpeningAssessment:
    ready: bool
    missing_categories: tuple[str, ...]
    pending_check_ids: tuple[str, ...]
    late_check_ids: tuple[str, ...]
    waived_check_ids: tuple[str, ...]


def assess_clinic_opening(
    checks: list[OpeningCheck],
    opens_at: str,
    required_categories: tuple[str, ...] = ("facilities", "inventory", "rooms", "staffing"),
) -> ClinicOpeningAssessment:
    """Validate accountable checklist completion before doors open."""
    opening = parse_time(opens_at, "opens_at")
    required = _categories(required_categories, "required opening category")
    seen: set[str] = set()
    covered: set[str] = set()
    pending: list[str] = []
    late: list[str] = []
    waived: list[str] = []
    for check in checks:
        check_id = clean_code(check.check_id, "opening check id")
        if check_id.casefold() in seen:
            raise DomainError(f"duplicate opening check id: {check_id}")
        seen.add(check_id.casefold())
        category = clean_code(check.category, "opening category")
        if category not in required:
            raise DomainError(f"opening check {check_id} has an unrequired category")
        owner = clean_text(check.owner, "opening check owner")
        due_at = parse_time(check.due_at, "due_at")
        if due_at > opening:
            raise DomainError(f"opening check {check_id} is due after opening")
        if not isinstance(check.status, OpeningCheckStatus):
            raise DomainError(f"opening check {check_id} has an invalid status")
        if check.status is OpeningCheckStatus.PENDING:
            if any(
                value is not None
                for value in (check.completed_at, check.completed_by, check.evidence, check.waiver_reason)
            ):
                raise DomainError(f"pending opening check {check_id} cannot contain completion details")
            pending.append(check_id)
            continue
        completed_at, completed_by = _completion(check, owner)
        if completed_at > opening:
            late.append(check_id)
        if check.status is OpeningCheckStatus.VERIFIED:
            if check.evidence is None or check.waiver_reason is not None:
                raise DomainError(f"verified opening check {check_id} requires evidence only")
            clean_text(check.evidence, "opening evidence", 500)
        else:
            if check.waiver_reason is None or check.evidence is not None:
                raise DomainError(f"waived opening check {check_id} requires a waiver reason only")
            if completed_by.casefold() == owner.casefold():
                raise DomainError(f"opening waiver {check_id} requires independent authority")
            clean_text(check.waiver_reason, "opening waiver reason", 500)
            waived.append(check_id)
        if completed_at <= opening:
            covered.add(category)
    missing = sorted(required - covered)
    pending.sort()
    late.sort()
    waived.sort()
    return ClinicOpeningAssessment(
        not missing and not pending, tuple(missing), tuple(pending), tuple(late), tuple(waived)
    )


def _completion(check: OpeningCheck, owner: str) -> tuple[datetime, str]:
    if check.completed_at is None or check.completed_by is None:
        raise DomainError(f"completed opening check {check.check_id} requires completion details")
    completed_at = parse_time(check.completed_at, "completed_at")
    completed_by = clean_text(check.completed_by, "opening completion actor")
    if completed_at < parse_time(check.due_at, "due_at") - _maximum_early_completion():
        raise DomainError(f"opening check {check.check_id} was completed implausibly early")
    return completed_at, completed_by


def _maximum_early_completion() -> timedelta:
    return timedelta(days=30)


def _categories(values: tuple[str, ...], field: str) -> set[str]:
    categories = {clean_code(value, field) for value in values}
    if not categories or len(categories) != len(values):
        raise DomainError(f"{field}s must be non-empty and unique")
    return categories
