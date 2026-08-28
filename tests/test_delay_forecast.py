from dataclasses import replace

import pytest

from clinicflow import AppointmentDelayInput, DomainError, forecast_appointment_delays


def visit(identifier: str, starts_at: str, ends_at: str, delay: int = 0) -> AppointmentDelayInput:
    return AppointmentDelayInput(identifier, "room-a", starts_at, ends_at, delay)


def test_propagates_delay_and_turnover_through_a_room() -> None:
    rows = forecast_appointment_delays(
        [
            visit("first", "2026-09-05T09:00:00+02:00", "2026-09-05T10:00:00+02:00", 30),
            visit("second", "2026-09-05T10:10:00+02:00", "2026-09-05T10:40:00+02:00"),
        ],
        {"room-a": 20},
        "2026-09-05T18:00:00+02:00",
    )
    by_id = {row.appointment_id: row for row in rows}
    assert by_id["first"].delay_minutes == 30
    assert by_id["second"].delay_minutes == 40
    assert by_id["second"].predicted_starts_at == "2026-09-05T10:50:00+02:00"


def test_prioritizes_closing_overruns_and_notification() -> None:
    rows = forecast_appointment_delays(
        [visit("late", "2026-09-05T17:30:00+02:00", "2026-09-05T18:00:00+02:00", 20)],
        {},
        "2026-09-05T18:00:00+02:00",
    )
    assert rows[0].closing_overrun_minutes == 20
    assert rows[0].notify is True


def test_rejects_duplicate_appointments_and_invalid_delay() -> None:
    row = visit("visit", "2026-09-05T09:00:00+02:00", "2026-09-05T10:00:00+02:00")
    with pytest.raises(DomainError, match="duplicate delay"):
        forecast_appointment_delays([row, row], {}, "2026-09-05T18:00:00+02:00")
    with pytest.raises(DomainError, match="initial delay"):
        forecast_appointment_delays([replace(row, initial_delay_minutes=-1)], {}, "2026-09-05T18:00:00+02:00")
