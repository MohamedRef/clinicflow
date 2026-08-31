from datetime import UTC, datetime, timedelta

from clinicflow import (
    LanguageSupportAssignment,
    LanguageSupportDemand,
    LanguageSupportShift,
    allocate_language_support,
)


def test_allocates_language_support_with_capacity() -> None:
    start = datetime(2026, 9, 1, 9, tzinfo=UTC)
    result = allocate_language_support(
        [
            LanguageSupportDemand("a-1", "Arabic", start, start + timedelta(minutes=30)),
            LanguageSupportDemand("a-2", "Arabic", start + timedelta(hours=1), start + timedelta(hours=1, minutes=30)),
            LanguageSupportDemand("a-3", "French", start, start + timedelta(minutes=30)),
        ],
        [LanguageSupportShift("staff-1", frozenset({"arabic"}), start, start + timedelta(hours=4), 1)],
    )
    assert result == [
        LanguageSupportAssignment("a-1", "staff-1", None),
        LanguageSupportAssignment("a-3", None, "no_qualified_shift"),
        LanguageSupportAssignment("a-2", None, "capacity_unavailable"),
    ]


def test_prefers_shift_with_more_remaining_capacity() -> None:
    start = datetime(2026, 9, 1, 9, tzinfo=UTC)
    result = allocate_language_support(
        [LanguageSupportDemand("a", "Arabic", start, start + timedelta(minutes=30))],
        [
            LanguageSupportShift("small", frozenset({"arabic"}), start, start + timedelta(hours=1), 1),
            LanguageSupportShift("large", frozenset({"arabic"}), start, start + timedelta(hours=1), 2),
        ],
    )
    assert result[0].staff_id == "large"
