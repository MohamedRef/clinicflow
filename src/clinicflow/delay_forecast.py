"""Room-level delay propagation for clinic appointment operations."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class AppointmentDelayInput:
    appointment_id: str
    room_id: str
    starts_at: str
    ends_at: str
    initial_delay_minutes: int


@dataclass(frozen=True, slots=True)
class AppointmentDelayForecast:
    appointment_id: str
    room_id: str
    predicted_starts_at: str
    predicted_ends_at: str
    delay_minutes: int
    notify: bool
    closing_overrun_minutes: int


def forecast_appointment_delays(
    appointments: list[AppointmentDelayInput],
    turnover_minutes: dict[str, int],
    clinic_closes_at: str,
    notification_threshold_minutes: int = 15,
) -> list[AppointmentDelayForecast]:
    """Propagate delays through each room while retaining scheduled duration."""
    closing = parse_time(clinic_closes_at, "clinic_closes_at")
    if (
        isinstance(notification_threshold_minutes, bool)
        or not isinstance(notification_threshold_minutes, int)
        or not 0 <= notification_threshold_minutes <= 240
    ):
        raise DomainError("notification threshold must be from 0 through 240 minutes")
    rules: dict[str, int] = {}
    for room_id, minutes in turnover_minutes.items():
        room = clean_code(room_id, "turnover room id")
        if isinstance(minutes, bool) or not isinstance(minutes, int) or not 0 <= minutes <= 240:
            raise DomainError("turnover minutes must be from 0 through 240")
        rules[room] = minutes

    seen: set[str] = set()
    by_room: dict[str, list[tuple[AppointmentDelayInput, datetime, datetime]]] = {}
    for appointment in appointments:
        appointment_id = clean_code(appointment.appointment_id, "delay appointment id")
        if appointment_id in seen:
            raise DomainError(f"duplicate delay appointment id: {appointment_id}")
        seen.add(appointment_id)
        room_id = clean_code(appointment.room_id, "delay room id")
        starts_at = parse_time(appointment.starts_at, "starts_at")
        ends_at = parse_time(appointment.ends_at, "ends_at")
        if ends_at <= starts_at:
            raise DomainError("appointment delay window must have positive duration")
        if (
            isinstance(appointment.initial_delay_minutes, bool)
            or not isinstance(appointment.initial_delay_minutes, int)
            or not 0 <= appointment.initial_delay_minutes <= 24 * 60
        ):
            raise DomainError("initial delay must be from 0 through 1440 minutes")
        normalized = AppointmentDelayInput(
            appointment_id,
            room_id,
            appointment.starts_at,
            appointment.ends_at,
            appointment.initial_delay_minutes,
        )
        by_room.setdefault(room_id, []).append((normalized, starts_at, ends_at))

    forecasts: list[AppointmentDelayForecast] = []
    for room_id, room_appointments in by_room.items():
        room_appointments.sort(key=lambda item: (item[1], item[0].appointment_id))
        previous_end: datetime | None = None
        for appointment, scheduled_start, scheduled_end in room_appointments:
            predicted_start = scheduled_start + timedelta(minutes=appointment.initial_delay_minutes)
            if previous_end is not None:
                predicted_start = max(predicted_start, previous_end + timedelta(minutes=rules.get(room_id, 15)))
            duration = scheduled_end - scheduled_start
            predicted_end = predicted_start + duration
            delay_minutes = int((predicted_start - scheduled_start) / timedelta(minutes=1))
            overrun = max(0, int((predicted_end - closing) / timedelta(minutes=1)))
            forecasts.append(
                AppointmentDelayForecast(
                    appointment.appointment_id,
                    room_id,
                    predicted_start.isoformat(),
                    predicted_end.isoformat(),
                    delay_minutes,
                    delay_minutes >= notification_threshold_minutes,
                    overrun,
                )
            )
            previous_end = predicted_end
    return sorted(forecasts, key=lambda item: (-item.closing_overrun_minutes, -item.delay_minutes, item.appointment_id))
