import pytest

from clinicflow import (
    DomainError,
    NoShowWaitlistCandidate,
    ReleasedNoShowSlot,
    recover_no_show_capacity,
)


def test_no_show_recovery_selects_highest_priority_eligible_candidate() -> None:
    slot = ReleasedNoShowSlot("slot", "clinic", "exam", 30, 60)
    candidates = [
        NoShowWaitlistCandidate("routine", "clinic", ("exam",), 20, 20, 1),
        NoShowWaitlistCandidate("urgent", "clinic", ("exam",), 25, 25, 5),
    ]
    got = recover_no_show_capacity([slot], candidates)
    assert got[0].appointment_id == "urgent"
    assert got[0].recovered_minutes == 25


def test_no_show_recovery_does_not_reuse_waiting_appointments() -> None:
    slots = [
        ReleasedNoShowSlot("first", "clinic", "exam", 30, 60),
        ReleasedNoShowSlot("second", "clinic", "exam", 60, 90),
    ]
    candidate = NoShowWaitlistCandidate("only", "clinic", ("exam",), 20, 20, 1)
    got = recover_no_show_capacity(slots, [candidate])
    assert got[0].appointment_id == "only"
    assert got[1].appointment_id is None


def test_no_show_recovery_rejects_duplicate_slots() -> None:
    slot = ReleasedNoShowSlot("same", "clinic", "exam", 30, 60)
    with pytest.raises(DomainError, match="duplicate"):
        recover_no_show_capacity([slot, slot], [])
