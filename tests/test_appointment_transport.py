from datetime import UTC, datetime

from clinicflow import AppointmentTransportRequest, TransportVehicle, plan_appointment_transport


def test_assigns_accessible_transport_once() -> None:
    rows = plan_appointment_transport(
        [AppointmentTransportRequest("a", "north", datetime(2026, 9, 4, 12, tzinfo=UTC), 2, 1)],
        [TransportVehicle("van", "north", 4, 1)],
    )
    assert rows[0].state == "assigned"
    assert rows[0].vehicle_id == "van"
