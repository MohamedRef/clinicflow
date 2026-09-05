from datetime import UTC, datetime, timedelta

import pytest

from clinicflow.appointment_resource_holds import (
    AppointmentDemand,
    AppointmentResource,
    AppointmentResourceBoard,
    HoldState,
    ResourceKind,
    ResourceRequirement,
)

NOW = datetime(2026, 9, 5, 8, tzinfo=UTC)


def test_holds_and_confirms_complete_resource_set_atomically() -> None:
    board = AppointmentResourceBoard(
        resources=(
            AppointmentResource("room-1", ResourceKind.ROOM, "site", ("accessible",), NOW, NOW + timedelta(days=1)),
            AppointmentResource("staff-1", ResourceKind.STAFF, "site", ("reception",), NOW, NOW + timedelta(days=1)),
        ),
        demands=(
            AppointmentDemand(
                "appointment-1",
                "site",
                NOW + timedelta(hours=2),
                NOW + timedelta(hours=3),
                5,
                (
                    ResourceRequirement("room", ResourceKind.ROOM, ("accessible",)),
                    ResourceRequirement("staff", ResourceKind.STAFF, ("reception",)),
                ),
            ),
        ),
    )
    holds = board.hold("appointment-1", NOW)
    confirmed = board.confirm("appointment-1", NOW + timedelta(minutes=5))
    assert len(holds) == 2
    assert {hold.state for hold in confirmed} == {HoldState.CONFIRMED}


def test_rejects_partial_atomic_hold_and_detects_conflicts() -> None:
    demand = AppointmentDemand(
        "appointment-1",
        "site",
        NOW + timedelta(hours=2),
        NOW + timedelta(hours=3),
        5,
        (ResourceRequirement("rooms", ResourceKind.ROOM, ("accessible",), 2),),
    )
    board = AppointmentResourceBoard(
        resources=(
            AppointmentResource("room-1", ResourceKind.ROOM, "site", ("accessible",), NOW, NOW + timedelta(days=1)),
        ),
        demands=(demand,),
    )
    assert board.plan("appointment-1", NOW).requirements[0].shortfall == 1
    with pytest.raises(ValueError, match="atomically"):
        board.hold("appointment-1", NOW)


def test_expires_unconfirmed_holds() -> None:
    board = AppointmentResourceBoard(
        resources=(AppointmentResource("room", ResourceKind.ROOM, "site", (), NOW, NOW + timedelta(days=1)),),
        demands=(
            AppointmentDemand(
                "appointment",
                "site",
                NOW + timedelta(hours=2),
                NOW + timedelta(hours=3),
                1,
                (ResourceRequirement("room", ResourceKind.ROOM, ()),),
            ),
        ),
    )
    board.hold("appointment", NOW, 5)
    assert board.expire(NOW + timedelta(minutes=6))[0].state is HoldState.EXPIRED
