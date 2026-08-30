import pytest

from clinicflow import (
    DomainError,
    FacilityInterruption,
    FacilityRoomUse,
    FacilityService,
    assess_facility_interruptions,
)


def test_facility_interruptions_distinguish_relocation_and_contingency() -> None:
    interruption = FacilityInterruption(
        "out-1", "clinic", FacilityService.NETWORK, "2026-08-30T10:00:00Z", "2026-08-30T12:00:00Z", ("room-1", "room-2")
    )
    bookings = [
        FacilityRoomUse("networked", "clinic", "room-1", "2026-08-30T10:30:00Z", "2026-08-30T11:00:00Z", True, False),
        FacilityRoomUse("offline", "clinic", "room-2", "2026-08-30T10:30:00Z", "2026-08-30T11:00:00Z", False, False),
    ]
    decisions = assess_facility_interruptions([interruption], bookings)
    assert [(item.booking_id, item.action) for item in decisions] == [
        ("networked", "relocate"),
        ("offline", "contingency"),
    ]


def test_facility_interruptions_reject_duplicates_and_empty_room_scope() -> None:
    interruption = FacilityInterruption(
        "out", "clinic", FacilityService.POWER, "2026-08-30T10:00:00Z", "2026-08-30T12:00:00Z", ("room",)
    )
    with pytest.raises(DomainError, match="duplicate facility interruption"):
        assess_facility_interruptions([interruption, interruption], [])
    with pytest.raises(DomainError, match="affected room"):
        assess_facility_interruptions(
            [
                FacilityInterruption(
                    "empty", "clinic", FacilityService.POWER, "2026-08-30T10:00:00Z", "2026-08-30T12:00:00Z", ()
                )
            ],
            [],
        )
