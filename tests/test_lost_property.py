from datetime import UTC, datetime

import pytest

from clinicflow import LostPropertyClaim, LostPropertyItem, assess_lost_property_release
from clinicflow.models import DomainError


def test_sensitive_property_requires_seal_identity_match_and_second_review() -> None:
    now = datetime(2026, 9, 4, tzinfo=UTC)
    rows = assess_lost_property_release(
        [LostPropertyItem("wallet", "safe", now, True, sensitive=True), LostPropertyItem("coat", "desk", now, True)],
        [LostPropertyClaim("wallet", "person", True, True, None), LostPropertyClaim("coat", "person", True, True)],
        as_of=now,
    )
    assert rows[0].blockers == ("second_reviewer_missing",)
    assert rows[1].decision == "release"


def test_rejects_claims_for_unknown_items_and_future_receipts() -> None:
    now = datetime(2026, 9, 4, tzinfo=UTC)
    with pytest.raises(DomainError, match="claim"):
        assess_lost_property_release([], [LostPropertyClaim("missing", "person", True, True)], as_of=now)
    with pytest.raises(DomainError, match="item"):
        assess_lost_property_release(
            [LostPropertyItem("item", "desk", datetime(2026, 9, 5, tzinfo=UTC), True)], [], as_of=now
        )
