from datetime import date

import pytest

from clinicflow import ReceptionPrintDemand, ReceptionPrintStock, allocate_reception_print_stock
from clinicflow.models import DomainError


def test_protects_high_priority_reception_desk() -> None:
    result = allocate_reception_print_stock(
        [ReceptionPrintDemand("routine", 100, 1, 1), ReceptionPrintDemand("urgent", 100, 1, 10)],
        [ReceptionPrintStock("lot", 100, 1, date(2026, 9, 30))],
        as_of=date(2026, 9, 4),
    )
    assert result[0].desk_id == "urgent" and result[0].ready
    assert not result[1].ready


def test_rejects_boolean_stock_quantity() -> None:
    with pytest.raises(DomainError, match="paper stock"):
        allocate_reception_print_stock(
            [], [ReceptionPrintStock("lot", True, 1, date(2026, 9, 30))], as_of=date(2026, 9, 4)
        )  # type: ignore[arg-type]
