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


def test_allocates_requested_stock_without_substitution() -> None:
    board = StockSubstitutionBoard()
    board.add_stock(
        StockItem(
            "linen", "site", "linen", 10, 2, NOW + timedelta(days=10), StockCriticality.ESSENTIAL, ("latex-free",)
        )
    )
    board.request(StockDemand("demand", "site", "linen", "linen", 5, NOW + timedelta(days=1), 5, ("latex-free",)))
    decision = board.decision("demand", NOW)
    assert decision.ready is True
    assert decision.units_available == 8
    assert board.allocate("demand", NOW).substituted is False
    with pytest.raises(ValueError, match="already allocated"):
        board.allocate("demand", NOW)


def test_expires_and_rejects_substitution_proposals() -> None:
    board = StockSubstitutionBoard()
    board.add_stock(StockItem("alt", "site", "linen", 2, 0, None, StockCriticality.ROUTINE, ()))
    board.request(StockDemand("demand", "site", "missing", "linen", 5, NOW + timedelta(days=1), 1, (), True))
    board.propose(
        SubstitutionProposal("proposal", "demand", "alt", NOW, "planner", NOW + timedelta(hours=1), "Temporary supply")
    )
    with pytest.raises(ValueError, match="independent"):
        board.approve("proposal", NOW + timedelta(minutes=1), "planner")
    assert board.expire(NOW + timedelta(hours=2))[0].state.value == "expired"
    with pytest.raises(ValueError, match="only proposed"):
        board.approve("proposal", NOW + timedelta(minutes=1), "manager")


def test_validates_stock_and_proposal_boundaries() -> None:
    board = StockSubstitutionBoard()
    with pytest.raises(ValueError, match="exceed"):
        board.add_stock(StockItem("sku", "site", "cat", 1, 2, None, StockCriticality.ROUTINE))
    board.add_stock(StockItem("sku", "site", "cat", 1, 0, NOW + timedelta(hours=1), StockCriticality.ROUTINE))
    board.request(StockDemand("demand", "site", "sku", "cat", 2, NOW + timedelta(hours=2), 1))
    decision = board.decision("demand", NOW)
    assert decision.ready is False
    assert any("expires before use" in blocker for blocker in decision.blockers)
    with pytest.raises(KeyError, match="unknown stock demand"):
        board.decision("missing", NOW)


def test_rejects_disallowed_and_late_substitutions() -> None:
    board = StockSubstitutionBoard()
    board.add_stock(StockItem("alt", "site", "cat", 3, 0, None, StockCriticality.ROUTINE))
    board.request(StockDemand("fixed", "site", "missing", "cat", 1, NOW + timedelta(hours=2), 1, (), False))
    with pytest.raises(ValueError, match="does not allow"):
        board.propose(
            SubstitutionProposal("p1", "fixed", "alt", NOW, "planner", NOW + timedelta(hours=1), "Alternative")
        )
    board.request(StockDemand("open", "site", "missing", "cat", 1, NOW + timedelta(hours=2), 1, (), True))
    with pytest.raises(ValueError, match="validity"):
        board.propose(SubstitutionProposal("p2", "open", "alt", NOW, "planner", NOW + timedelta(hours=3), "Too late"))
    proposal = board.propose(
        SubstitutionProposal("p3", "open", "alt", NOW, "planner", NOW + timedelta(hours=1), "Valid")
    )
    assert board.reject(proposal.proposal_id, NOW + timedelta(minutes=1), "Not required").state.value == "rejected"
    with pytest.raises(ValueError, match="only active"):
        board.reject(proposal.proposal_id, NOW + timedelta(minutes=2), "Again")


def test_rejects_duplicate_stock_and_demand_records() -> None:
    board = StockSubstitutionBoard()
    item = StockItem("sku", "site", "cat", 1, 0, None, StockCriticality.ROUTINE)
    board.add_stock(item)
    with pytest.raises(ValueError, match="duplicate site stock"):
        board.add_stock(item)
    demand = StockDemand("demand", "site", "sku", "cat", 1, NOW + timedelta(hours=1), 1)
    board.request(demand)
    with pytest.raises(ValueError, match="duplicate stock demand"):
        board.request(demand)
    with pytest.raises(KeyError, match="unknown substitution proposal"):
        board.approve("missing", NOW, "manager")
