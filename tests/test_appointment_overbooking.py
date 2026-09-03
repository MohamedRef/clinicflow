import pytest

from clinicflow import DomainError, OverbookingRequest, OverbookingSlot, plan_appointment_overbooking


def request(identifier: str, probability: float, priority: int = 3) -> OverbookingRequest:
    return OverbookingRequest(identifier, "morning", probability, priority, "2026-08-28T08:00:00+03:00")


def test_prioritizes_high_risk_absence_requests_within_safety_capacity() -> None:
    slot = OverbookingSlot("morning", "room-a", "2026-09-01T09:00:00+03:00", "2026-09-01T10:00:00+03:00", 2, 3, 0.7)
    rows = plan_appointment_overbooking(
        [slot], [request("low-risk", 0.2, 5), request("eligible", 0.8, 4), request("full", 0.9, 3)], {"morning": 2}
    )
    assert [(row.request_id, row.accepted, row.reason) for row in rows] == [
        ("low-risk", False, "attendance risk too high"),
        ("eligible", True, "controlled overbooking approved"),
        ("full", False, "maximum capacity reached"),
    ]


def test_rejects_duplicate_requests_and_impossible_occupancy() -> None:
    slot = OverbookingSlot("morning", "room-a", "2026-09-01T09:00:00+03:00", "2026-09-01T10:00:00+03:00", 2, 3, 0.7)
    row = request("same", 0.8)
    with pytest.raises(DomainError, match="duplicate overbooking request"):
        plan_appointment_overbooking([slot], [row, row], {})
    with pytest.raises(DomainError, match="exceed maximum"):
        plan_appointment_overbooking([slot], [], {"morning": 4})


@pytest.mark.parametrize("probability", [float("nan"), float("inf"), float("-inf")])
def test_rejects_non_finite_absence_probabilities(probability: float) -> None:
    slot = OverbookingSlot(
        "morning", "room-a", "2026-09-01T09:00:00+03:00", "2026-09-01T10:00:00+03:00", 2, 3, probability
    )
    with pytest.raises(DomainError, match="maximum absence probability"):
        plan_appointment_overbooking([slot], [], {})

    valid_slot = OverbookingSlot(
        "morning", "room-a", "2026-09-01T09:00:00+03:00", "2026-09-01T10:00:00+03:00", 2, 3, 0.7
    )
    with pytest.raises(DomainError, match="absence probability"):
        plan_appointment_overbooking([valid_slot], [request("invalid", probability)], {})
