from datetime import UTC, datetime, timedelta

import pytest

from clinicflow import AppointmentReminder, ReminderDelivery, reconcile_appointment_reminders
from clinicflow.models import DomainError


def test_reports_missing_late_and_unacknowledged_channels() -> None:
    appointment = datetime(2026, 9, 5, 10, tzinfo=UTC)
    rows = reconcile_appointment_reminders(
        [AppointmentReminder("a", appointment, ("sms", "email"), 24)],
        [ReminderDelivery("a", "sms", appointment - timedelta(hours=2), False)],
    )
    assert rows[0].missing_channels == ("email",)
    assert rows[0].late_channels == ("sms",)
    assert rows[0].unacknowledged_channels == ("sms",)


def test_rejects_delivery_after_appointment() -> None:
    appointment = datetime(2026, 9, 5, 10, tzinfo=UTC)
    with pytest.raises(DomainError, match="invalid"):
        reconcile_appointment_reminders(
            [AppointmentReminder("a", appointment, ("sms",), 1)], [ReminderDelivery("a", "sms", appointment, True)]
        )
