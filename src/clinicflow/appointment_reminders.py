"""Reconcile non-clinical appointment reminder delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from clinicflow.models import DomainError


@dataclass(frozen=True, slots=True)
class AppointmentReminder:
    appointment_id: str
    appointment_at: datetime
    required_channels: tuple[str, ...]
    minimum_lead_hours: int


@dataclass(frozen=True, slots=True)
class ReminderDelivery:
    appointment_id: str
    channel: str
    delivered_at: datetime
    acknowledged: bool


@dataclass(frozen=True, slots=True)
class ReminderFinding:
    appointment_id: str
    missing_channels: tuple[str, ...]
    late_channels: tuple[str, ...]
    unacknowledged_channels: tuple[str, ...]
    ready: bool


def reconcile_appointment_reminders(
    reminders: list[AppointmentReminder], deliveries: list[ReminderDelivery]
) -> list[ReminderFinding]:
    """Check channel coverage, lead time, and acknowledgement."""
    configured: dict[str, AppointmentReminder] = {}
    for reminder in reminders:
        appointment_id = _text(reminder.appointment_id, "reminder appointment", maximum=120)
        key = appointment_id.casefold()
        channels = tuple(
            dict.fromkeys(
                _text(value, "reminder channel", maximum=40).casefold() for value in reminder.required_channels
            )
        )
        appointment_at = _checked_time(reminder.appointment_at, "reminder appointment time")
        if key in configured or not channels or reminder.minimum_lead_hours < 0:
            raise DomainError(f"invalid or duplicate reminder requirement {appointment_id}")
        configured[key] = AppointmentReminder(appointment_id, appointment_at, channels, reminder.minimum_lead_hours)
    received: dict[tuple[str, str], ReminderDelivery] = {}
    for delivery in deliveries:
        appointment_id = _text(delivery.appointment_id, "reminder delivery appointment", maximum=120)
        key = appointment_id.casefold()
        requirement = configured.get(key)
        channel = _text(delivery.channel, "reminder delivery channel", maximum=40).casefold()
        if requirement is None or channel not in requirement.required_channels:
            raise DomainError(f"unexpected reminder delivery {appointment_id}/{channel}")
        identity = (key, channel)
        delivered_at = _checked_time(delivery.delivered_at, "reminder delivery time")
        if identity in received or delivered_at >= requirement.appointment_at:
            raise DomainError(f"invalid or duplicate reminder delivery {appointment_id}/{channel}")
        received[identity] = ReminderDelivery(appointment_id, channel, delivered_at, delivery.acknowledged)
    findings: list[ReminderFinding] = []
    for key, reminder in configured.items():
        missing = tuple(channel for channel in reminder.required_channels if (key, channel) not in received)
        late = tuple(
            channel
            for channel in reminder.required_channels
            if (row := received.get((key, channel)))
            and (reminder.appointment_at - row.delivered_at).total_seconds() < reminder.minimum_lead_hours * 3600
        )
        unacknowledged = tuple(
            channel
            for channel in reminder.required_channels
            if (row := received.get((key, channel))) and not row.acknowledged
        )
        findings.append(
            ReminderFinding(
                reminder.appointment_id, missing, late, unacknowledged, not missing and not late and not unacknowledged
            )
        )
    return sorted(
        findings, key=lambda row: (row.ready, -(len(row.missing_channels) + len(row.late_channels)), row.appointment_id)
    )


def _text(value: str, field: str, *, maximum: int) -> str:
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > maximum:
        raise DomainError(f"{field} is invalid")
    return normalized


def _checked_time(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DomainError(f"{field} must include a timezone")
    return value
