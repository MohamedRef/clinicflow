"""Inventory recall isolation across non-clinical clinic rooms."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class RecallIsolationStatus(StrEnum):
    ESCALATE = "escalate"
    BLOCKED = "blocked"
    ISOLATED = "isolated"


@dataclass(frozen=True, slots=True)
class RecallRoomPosition:
    lot_id: str
    room_id: str
    units_recorded: int
    units_removed: int
    sweep_completed_minute: int | None
    seal_verified: bool


@dataclass(frozen=True, slots=True)
class RecallIsolationFinding:
    lot_id: str
    room_id: str
    status: RecallIsolationStatus
    units_unaccounted: int
    reasons: tuple[str, ...]
    sweep_age_minutes: int | None


def _identifier(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"recall isolation {field} is required")
    return normalized


def assess_recall_isolation(
    positions: Iterable[RecallRoomPosition],
    *,
    review_minute: int,
    maximum_sweep_age_minutes: int,
) -> tuple[RecallIsolationFinding, ...]:
    """Assess recalled lots without allowing units to disappear between rooms."""
    if review_minute <= 0 or maximum_sweep_age_minutes <= 0:
        raise ValueError("recall isolation review controls must be positive")
    seen: set[tuple[str, str]] = set()
    findings: list[RecallIsolationFinding] = []

    for position in positions:
        lot_id = _identifier(position.lot_id, "lot")
        room_id = _identifier(position.room_id, "room")
        identity = (lot_id.casefold(), room_id.casefold())
        if identity in seen:
            raise ValueError(f"duplicate recall room position: {lot_id}/{room_id}")
        seen.add(identity)
        if position.units_recorded < 0 or not 0 <= position.units_removed <= position.units_recorded:
            raise ValueError(f"invalid recall quantities for {lot_id}/{room_id}")
        if position.sweep_completed_minute is not None and not (0 < position.sweep_completed_minute <= review_minute):
            raise ValueError(f"invalid recall sweep time for {lot_id}/{room_id}")

        missing_units = position.units_recorded - position.units_removed
        age = None if position.sweep_completed_minute is None else review_minute - position.sweep_completed_minute
        reasons: list[str] = []
        if position.sweep_completed_minute is None:
            reasons.append("room sweep missing")
        if missing_units:
            reasons.append("recalled units unaccounted")
        if not position.seal_verified:
            reasons.append("quarantine seal unverified")

        if missing_units:
            status = RecallIsolationStatus.ESCALATE
        elif reasons:
            status = RecallIsolationStatus.BLOCKED
        elif age is not None and age > maximum_sweep_age_minutes:
            status = RecallIsolationStatus.BLOCKED
            reasons.append("room sweep is stale")
        else:
            status = RecallIsolationStatus.ISOLATED
        findings.append(
            RecallIsolationFinding(
                lot_id=lot_id,
                room_id=room_id,
                status=status,
                units_unaccounted=missing_units,
                reasons=tuple(reasons),
                sweep_age_minutes=age,
            )
        )

    priority = {RecallIsolationStatus.ESCALATE: 0, RecallIsolationStatus.BLOCKED: 1, RecallIsolationStatus.ISOLATED: 2}
    return tuple(
        sorted(
            findings,
            key=lambda finding: (
                priority[finding.status],
                -finding.units_unaccounted,
                finding.lot_id.casefold(),
                finding.room_id.casefold(),
            ),
        )
    )
