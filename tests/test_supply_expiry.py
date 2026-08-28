import pytest

from clinicflow import DomainError, ExpiringSupplyBatch, ScheduledSupplyDemand, allocate_expiring_supplies


def test_allocates_first_expiring_usable_batches_to_earliest_demand() -> None:
    batches = [
        ExpiringSupplyBatch("late", "mask", 6, "2026-09-30T00:00:00+03:00"),
        ExpiringSupplyBatch("early", "mask", 4, "2026-09-10T00:00:00+03:00"),
        ExpiringSupplyBatch("quarantine", "mask", 20, "2026-09-05T00:00:00+03:00", True),
    ]
    rows = allocate_expiring_supplies(
        batches,
        [
            ScheduledSupplyDemand("first", "mask", 7, "2026-09-01T09:00:00+03:00", 4),
            ScheduledSupplyDemand("second", "mask", 5, "2026-09-02T09:00:00+03:00", 3),
        ],
    )
    assert rows[0].allocations == (("early", 4), ("late", 3))
    assert rows[0].fulfilled
    assert rows[1].shortage == 2


def test_rejects_duplicate_batches_and_invalid_demand_priority() -> None:
    batch = ExpiringSupplyBatch("same", "mask", 2, "2026-09-30T00:00:00+03:00")
    with pytest.raises(DomainError, match="duplicate supply batch"):
        allocate_expiring_supplies([batch, batch], [])
    with pytest.raises(DomainError, match="priority"):
        allocate_expiring_supplies([], [ScheduledSupplyDemand("d", "mask", 1, "2026-09-01T00:00:00+03:00", 0)])
