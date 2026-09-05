from datetime import UTC, datetime, timedelta

import pytest

from clinicflow.stock_substitution import (
    StockCriticality,
    StockDemand,
    StockItem,
    StockSubstitutionBoard,
    SubstitutionProposal,
)

NOW = datetime(2026, 9, 5, 8, tzinfo=UTC)


def test_approves_and_allocates_compatible_substitute() -> None:
    board = StockSubstitutionBoard()
    board.add_stock(
        StockItem("alt", "site", "linen", 20, 0, NOW + timedelta(days=30), StockCriticality.IMPORTANT, ("latex-free",))
    )
    board.request(
        StockDemand("demand", "site", "missing", "linen", 5, NOW + timedelta(days=1), 9, ("latex-free",), True)
    )
    board.propose(
        SubstitutionProposal(
            "proposal", "demand", "alt", NOW, "planner", NOW + timedelta(hours=12), "Equivalent specification"
        )
    )
    board.approve("proposal", NOW + timedelta(hours=1), "manager")
    allocation = board.allocate("demand", NOW + timedelta(hours=2))
    assert allocation.sku == "alt"
    assert allocation.substituted is True


def test_rejects_self_approval_and_incompatible_substitute() -> None:
    board = StockSubstitutionBoard()
    board.add_stock(StockItem("alt", "site", "linen", 20, 0, None, StockCriticality.ROUTINE, ()))
    board.request(
        StockDemand("demand", "site", "missing", "linen", 5, NOW + timedelta(days=1), 1, ("latex-free",), True)
    )
    with pytest.raises(ValueError, match="unsafe"):
        board.propose(
            SubstitutionProposal(
                "proposal", "demand", "alt", NOW, "planner", NOW + timedelta(hours=1), "Try alternative"
            )
        )


def test_reports_priority_order_for_unresolved_shortages() -> None:
    board = StockSubstitutionBoard()
    board.request(StockDemand("low", "site", "a", "linen", 1, NOW + timedelta(days=1), 1))
    board.request(StockDemand("high", "site", "b", "linen", 1, NOW + timedelta(days=1), 9))
    assert [item.demand_id for item in board.shortage_queue(NOW)] == ["high", "low"]
