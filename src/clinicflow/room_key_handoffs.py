"""Reconcile physical room-key handoffs across clinic shifts."""

from dataclasses import dataclass
from datetime import datetime

from clinicflow.models import DomainError


@dataclass(frozen=True, slots=True)
class RoomKeyHandoff:
    key_id: str
    room_id: str
    issued_to: str
    issued_at: datetime
    returned_at: datetime | None


@dataclass(frozen=True, slots=True)
class RoomKeyFinding:
    key_id: str
    room_id: str
    holder: str
    state: str


def assess_room_key_handoffs(handoffs: list[RoomKeyHandoff], *, as_of: datetime) -> list[RoomKeyFinding]:
    """Report outstanding and overdue room keys at a review instant."""
    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        raise DomainError("room key review must be timezone-aware")
    seen: set[str] = set()
    findings: list[RoomKeyFinding] = []
    for handoff in handoffs:
        key_id, room_id, holder = handoff.key_id.strip(), handoff.room_id.strip(), handoff.issued_to.strip()
        if not key_id or not room_id or not holder or key_id.casefold() in seen:
            raise DomainError("invalid or duplicate room key handoff")
        seen.add(key_id.casefold())
        if handoff.issued_at.tzinfo is None or handoff.issued_at > as_of:
            raise DomainError("invalid room key issue time")
        if handoff.returned_at is not None and (
            handoff.returned_at.tzinfo is None or handoff.returned_at < handoff.issued_at or handoff.returned_at > as_of
        ):
            raise DomainError("invalid room key return time")
        elapsed_hours = int((as_of - handoff.issued_at).total_seconds() // 3600)
        state = "returned" if handoff.returned_at else "overdue" if elapsed_hours >= 12 else "issued"
        findings.append(RoomKeyFinding(key_id, room_id, holder, state))
    order = {"overdue": 0, "issued": 1, "returned": 2}
    return sorted(findings, key=lambda row: (order[row.state], row.key_id))
