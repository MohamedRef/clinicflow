"""Deterministic appointment confirmation follow-up."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from .models import DomainError, clean_code, parse_time


class ConfirmationStatus(StrEnum):
    CONFIRMED = "confirmed"
    PENDING = "pending"
    OVERDUE = "overdue"
    CONTACT_EXHAUSTED = "contact_exhausted"


@dataclass(frozen=True, slots=True)
class ConfirmationCase:
    appointment_id: str
    starts_at: str
    confirmation_due_at: str
    contact_allowed: bool
    contact_attempts: int
    max_contact_attempts: int
    confirmed_at: str | None = None


@dataclass(frozen=True, slots=True)
class ConfirmationState:
    appointment_id: str
    status: ConfirmationStatus
    attempts_remaining: int
    minutes_overdue: int
    next_action: str


def review_confirmations(cases: list[ConfirmationCase], reviewed_at: str) -> list[ConfirmationState]:
    """Classify confirmation cases and prioritize operational follow-up."""
    review_time = parse_time(reviewed_at, "reviewed_at")
    seen: set[str] = set()
    states: list[ConfirmationState] = []
    for case in cases:
        appointment_id = clean_code(case.appointment_id, "confirmation appointment id")
        key = appointment_id.casefold()
        if key in seen:
            raise DomainError(f"duplicate confirmation appointment id: {appointment_id}")
        seen.add(key)
        starts_at = parse_time(case.starts_at, "starts_at")
        due_at = parse_time(case.confirmation_due_at, "confirmation_due_at")
        if due_at >= starts_at:
            raise DomainError("confirmation due time must be before appointment start")
        attempts = _attempt_count(case.contact_attempts, "contact attempts", allow_zero=True)
        maximum = _attempt_count(case.max_contact_attempts, "max contact attempts", allow_zero=False)
        if attempts > maximum:
            raise DomainError("contact attempts cannot exceed maximum")
        confirmed_at = _confirmed_time(case.confirmed_at, due_at, starts_at)
        states.append(
            _state_for_case(
                appointment_id,
                case.contact_allowed,
                attempts,
                maximum,
                confirmed_at,
                due_at,
                review_time,
            )
        )
    priority = {
        ConfirmationStatus.CONTACT_EXHAUSTED: 0,
        ConfirmationStatus.OVERDUE: 1,
        ConfirmationStatus.PENDING: 2,
        ConfirmationStatus.CONFIRMED: 3,
    }
    return sorted(states, key=lambda item: (priority[item.status], -item.minutes_overdue, item.appointment_id))


def _attempt_count(value: int, field: str, *, allow_zero: bool) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= 20:
        raise DomainError(f"{field} must be from {minimum} through 20")
    return value


def _confirmed_time(value: str | None, due_at: datetime, starts_at: datetime) -> datetime | None:
    if value is None:
        return None
    confirmed_at = parse_time(value, "confirmed_at")
    if confirmed_at >= starts_at:
        raise DomainError("confirmation must occur before appointment start")
    if confirmed_at < due_at - timedelta(days=365):
        raise DomainError("confirmation is implausibly early")
    return confirmed_at


def _state_for_case(
    appointment_id: str,
    contact_allowed: bool,
    attempts: int,
    maximum: int,
    confirmed_at: datetime | None,
    due_at: datetime,
    reviewed_at: datetime,
) -> ConfirmationState:
    remaining = maximum - attempts
    overdue = max(0, int((reviewed_at - due_at).total_seconds() // 60))
    if confirmed_at is not None:
        return ConfirmationState(appointment_id, ConfirmationStatus.CONFIRMED, remaining, 0, "none")
    if not contact_allowed or remaining == 0:
        action = "manual_review" if not contact_allowed else "release_or_escalate"
        return ConfirmationState(
            appointment_id,
            ConfirmationStatus.CONTACT_EXHAUSTED,
            remaining,
            overdue,
            action,
        )
    if reviewed_at >= due_at:
        return ConfirmationState(
            appointment_id,
            ConfirmationStatus.OVERDUE,
            remaining,
            overdue,
            "contact_now",
        )
    return ConfirmationState(appointment_id, ConfirmationStatus.PENDING, remaining, 0, "wait_until_due")
