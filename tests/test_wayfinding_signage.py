import pytest

from clinicflow import WayfindingObservation, WayfindingRequirement, assess_wayfinding_signage
from clinicflow.models import DomainError


def test_reports_missing_decision_signs_and_accessible_symbols() -> None:
    rows = assess_wayfinding_signage(
        [WayfindingRequirement("route", "temporary reception", 3, accessible_route=True)],
        [WayfindingObservation("ROUTE", 2, accessible_symbols=False, destination_matches=True)],
    )
    assert rows[0].missing_signs == 1
    assert rows[0].blockers == ("decision_point_signs_missing", "accessible_symbols_missing")


def test_rejects_unknown_and_duplicate_observations() -> None:
    with pytest.raises(DomainError, match="invalid"):
        assess_wayfinding_signage([], [WayfindingObservation("missing", 1, True, True)])
    requirement = WayfindingRequirement("route", "room", 1)
    observation = WayfindingObservation("route", 1, True, True)
    with pytest.raises(DomainError, match="duplicate"):
        assess_wayfinding_signage([requirement], [observation, observation])
