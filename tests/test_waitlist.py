import pytest

from clinicflow import ReleasedSlot, WaitlistRequest, match_waitlist
from clinicflow.models import DomainError


def request(
    identifier: str, priority: int, capabilities: set[str], latest: str = "2026-09-01T14:00:00+00:00"
) -> WaitlistRequest:
    return WaitlistRequest(
        identifier, f"patient-{identifier}", "Consult", capabilities, "2026-09-01T08:00:00+00:00", latest, priority
    )


def slot(identifier: str, starts: str, capabilities: set[str]) -> ReleasedSlot:
    return ReleasedSlot(identifier, "room-1", capabilities, starts, "2026-09-01T10:00:00+00:00")


def test_matches_priority_then_deadline_without_reusing_requests() -> None:
    matches = match_waitlist(
        [request("low", 2, {"exam"}), request("urgent", 5, {"exam"}), request("special", 5, {"imaging"})],
        [
            slot("general", "2026-09-01T09:00:00+00:00", {"exam"}),
            ReleasedSlot(
                "imaging", "room-2", {"exam", "imaging"}, "2026-09-01T10:00:00+00:00", "2026-09-01T11:00:00+00:00"
            ),
        ],
    )
    assert [(item.request_id, item.slot_id) for item in matches] == [("urgent", "general"), ("special", "imaging")]


def test_skips_slots_outside_request_window_or_capability() -> None:
    matches = match_waitlist(
        [request("candidate", 4, {"imaging"}, "2026-09-01T09:30:00+00:00")],
        [slot("wrong-capability", "2026-09-01T09:00:00+00:00", {"exam"})],
    )
    assert matches == []


def test_matches_against_canonical_slot_identity_and_capabilities() -> None:
    matches = match_waitlist(
        [request("candidate", 4, {"exam"})],
        [slot(" SLOT_A ", "2026-09-01T09:00:00+00:00", {" EXAM "})],
    )
    assert [(item.request_id, item.slot_id) for item in matches] == [("candidate", "slot_a")]


@pytest.mark.parametrize(
    "requests,slots,message",
    [
        ([request("same", 1, set()), request("same", 2, set())], [], "duplicate waitlist"),
        ([request("bad", 0, set())], [], "window and priority"),
        (
            [],
            [slot("same", "2026-09-01T09:00:00+00:00", set()), slot("same", "2026-09-01T09:00:00+00:00", set())],
            "duplicate released",
        ),
    ],
)
def test_invalid_waitlist_inputs_fail_closed(
    requests: list[WaitlistRequest], slots: list[ReleasedSlot], message: str
) -> None:
    with pytest.raises(DomainError, match=message):
        match_waitlist(requests, slots)
