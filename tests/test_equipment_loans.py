from dataclasses import replace

import pytest

from clinicflow import DomainError, EquipmentLoanRequest, LoanEquipment, allocate_equipment_loans


def asset(identifier: str = "asset-a") -> LoanEquipment:
    return LoanEquipment(
        identifier, "monitor", "2026-09-02T08:00:00+02:00", "2026-09-02T18:00:00+02:00", "2026-08-25T08:00:00+02:00"
    )


def request(identifier: str = "request-a", priority: int = 3) -> EquipmentLoanRequest:
    return EquipmentLoanRequest(
        identifier, "appointment-a", "monitor", "2026-09-02T10:00:00+02:00", "2026-09-02T11:00:00+02:00", priority
    )


def test_allocates_inspected_equipment_and_prevents_overbooking() -> None:
    rows = allocate_equipment_loans(
        [request("routine", 1), request("urgent", 5)],
        [asset()],
        "2026-09-01T08:00:00+02:00",
    )
    assert rows[0].request_id == "urgent"
    assert rows[0].assigned is True
    assert rows[1].assigned is False


def test_allows_non_overlapping_loans_on_one_asset() -> None:
    later = replace(request("later"), starts_at="2026-09-02T12:00:00+02:00", ends_at="2026-09-02T13:00:00+02:00")
    rows = allocate_equipment_loans([request(), later], [asset()], "2026-09-01T08:00:00+02:00")
    assert [row.assigned for row in rows] == [True, True]


def test_rejects_duplicate_assets_and_invalid_priority() -> None:
    with pytest.raises(DomainError, match="duplicate loan asset"):
        allocate_equipment_loans([], [asset("Asset-A"), asset("asset-a")], "2026-09-01T08:00:00+02:00")
    with pytest.raises(DomainError, match="priority"):
        allocate_equipment_loans([replace(request(), priority=0)], [asset()], "2026-09-01T08:00:00+02:00")
