from datetime import UTC, datetime, timedelta

import pytest

from clinicflow.appointment_resource_holds import (
    AppointmentDemand,
    AppointmentResource,
    AppointmentResourceBoard,
    HoldState,
    ResourceHold,
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


def test_releases_confirmed_holds_and_excludes_conflicting_rooms() -> None:
    resource = AppointmentResource("room", ResourceKind.ROOM, "site", ("quiet",), NOW, NOW + timedelta(days=1))
    first = AppointmentDemand(
        "first",
        "site",
        NOW + timedelta(hours=2),
        NOW + timedelta(hours=3),
        1,
        (ResourceRequirement("room", ResourceKind.ROOM, ("quiet",)),),
    )
    second = AppointmentDemand(
        "second",
        "site",
        NOW + timedelta(hours=2),
        NOW + timedelta(hours=3),
        1,
        (ResourceRequirement("room", ResourceKind.ROOM, ("quiet",)),),
    )
    board = AppointmentResourceBoard(resources=(resource,), demands=(first, second))
    board.hold("first", NOW)
    assert board.plan("second", NOW).ready is False
    board.confirm("first", NOW + timedelta(minutes=1))
    released = board.release("first", NOW + timedelta(minutes=2))
    assert released[0].state is HoldState.RELEASED
    assert board.plan("second", NOW + timedelta(minutes=3)).ready is True


def test_validates_resource_demand_and_hold_boundaries() -> None:
    with pytest.raises(ValueError, match="end must follow"):
        AppointmentResourceBoard(resources=(AppointmentResource("r", ResourceKind.ROOM, "s", (), NOW, NOW),))
    with pytest.raises(ValueError, match="at least one"):
        AppointmentResourceBoard(demands=(AppointmentDemand("a", "s", NOW, NOW + timedelta(hours=1), 1, ()),))
    with pytest.raises(ValueError, match="duplicate appointment requirement"):
        AppointmentResourceBoard(
            demands=(
                AppointmentDemand(
                    "a",
                    "s",
                    NOW,
                    NOW + timedelta(hours=1),
                    1,
                    (ResourceRequirement("r", ResourceKind.ROOM, ()), ResourceRequirement("R", ResourceKind.ROOM, ())),
                ),
            )
        )
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
    board.hold("appointment", NOW, 1)
    with pytest.raises(ValueError, match="complete live hold"):
        board.confirm("appointment", NOW + timedelta(minutes=2))
    with pytest.raises(KeyError, match="unknown appointment"):
        board.plan("missing", NOW)


def test_loads_existing_holds_and_validates_identity_constraints() -> None:
    resource = AppointmentResource("room", ResourceKind.ROOM, "site", ("quiet",), NOW, NOW + timedelta(days=1))
    demand = AppointmentDemand(
        "appointment",
        "site",
        NOW + timedelta(hours=2),
        NOW + timedelta(hours=3),
        1,
        (ResourceRequirement("room", ResourceKind.ROOM, ("quiet",)),),
    )
    hold = ResourceHold("hold", "appointment", "room", "room", NOW, NOW + timedelta(minutes=10), HoldState.HELD)
    board = AppointmentResourceBoard((resource,), (demand,), (hold,))
    assert board.confirm("appointment", NOW + timedelta(minutes=1))[0].state is HoldState.CONFIRMED
    with pytest.raises(ValueError, match="duplicate appointment resource"):
        board.add_resource(resource)
    with pytest.raises(ValueError, match="duplicate appointment demand"):
        board.add_demand(demand)
    with pytest.raises(KeyError, match="unknown appointment resource"):
        board.conflicts("missing", NOW, NOW + timedelta(hours=1))


@pytest.mark.parametrize(
    ("resource", "message"),
    (
        (AppointmentResource(" ", ResourceKind.ROOM, "site", (), NOW, NOW + timedelta(hours=1)), "required"),
        (AppointmentResource("r", ResourceKind.ROOM, "site", ("a", "A"), NOW, NOW + timedelta(hours=1)), "duplicate"),
    ),
)
def test_rejects_invalid_resource_declarations(resource: AppointmentResource, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        AppointmentResourceBoard(resources=(resource,))


def test_rejects_invalid_hold_chronology_and_requirement_kind() -> None:
    resource = AppointmentResource("staff", ResourceKind.STAFF, "site", (), NOW, NOW + timedelta(days=1))
    demand = AppointmentDemand(
        "appointment",
        "site",
        NOW + timedelta(hours=1),
        NOW + timedelta(hours=2),
        1,
        (ResourceRequirement("room", ResourceKind.ROOM, ()),),
    )
    with pytest.raises(ValueError, match="expiry"):
        AppointmentResourceBoard(
            (resource,), (demand,), (ResourceHold("hold", "appointment", "room", "staff", NOW, NOW, HoldState.HELD),)
        )
    with pytest.raises(ValueError, match="kind"):
        AppointmentResourceBoard(
            (resource,),
            (demand,),
            (ResourceHold("hold", "appointment", "room", "staff", NOW, NOW + timedelta(minutes=1), HoldState.HELD),),
        )
