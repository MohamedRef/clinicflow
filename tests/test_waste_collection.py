import pytest

from clinicflow import ClinicWasteDemand, DomainError, WasteCourierShift, schedule_waste_collections


def test_waste_collections_prioritize_urgent_demand() -> None:
    shift = WasteCourierShift("courier", "clinic", ("general",), 10, 10, 60)
    demands = [
        ClinicWasteDemand("routine", "clinic", "general", 5, 10, 40, 20, 1),
        ClinicWasteDemand("urgent", "clinic", "general", 5, 10, 30, 20, 5),
    ]
    got = schedule_waste_collections(demands, [shift])
    assert got[0].collection_id == "urgent" and got[0].assigned
    assert not got[1].assigned


def test_waste_collections_reject_incompatible_streams() -> None:
    got = schedule_waste_collections(
        [ClinicWasteDemand("pickup", "clinic", "sharps", 1, 10, 30, 10, 1)],
        [WasteCourierShift("courier", "clinic", ("general",), 10, 10, 60)],
    )
    assert not got[0].assigned


def test_waste_collections_reject_duplicate_demands() -> None:
    demand = ClinicWasteDemand("pickup", "clinic", "general", 1, 10, 30, 10, 1)
    with pytest.raises(DomainError, match="duplicated"):
        schedule_waste_collections([demand, demand], [])
