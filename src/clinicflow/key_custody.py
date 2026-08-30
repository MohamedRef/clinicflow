"""Track custody and overdue return of restricted clinic keys."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .models import DomainError, clean_code, clean_text, parse_time


class KeyCustodyEventType(StrEnum):
    ISSUED = "issued"
    RETURNED = "returned"


@dataclass(frozen=True, slots=True)
class KeyCustodyEvent:
    event_id: str
    key_id: str
    event_type: KeyCustodyEventType
    custodian: str
    occurred_at: str
    due_at: str | None


@dataclass(frozen=True, slots=True)
class KeyCustodyPosition:
    key_id: str
    custodian: str | None
    issued_at: str | None
    due_at: str | None
    overdue: bool


def reconcile_key_custody(events: list[KeyCustodyEvent], as_of: str) -> list[KeyCustodyPosition]:
    """Replay custody events and report active or returned key positions."""
    observed_at = parse_time(as_of, "key custody as_of")
    event_ids: set[str] = set()
    normalized: list[tuple[KeyCustodyEvent, datetime]] = []
    for event in events:
        event_id = clean_code(event.event_id, "key custody event id")
        if event_id.casefold() in event_ids:
            raise DomainError(f"duplicate key custody event: {event_id}")
        event_ids.add(event_id.casefold())
        key_id = clean_code(event.key_id, "clinic key id")
        custodian = clean_text(event.custodian, "key custodian")
        if not isinstance(event.event_type, KeyCustodyEventType):
            raise DomainError("key custody event type is invalid")
        occurred = parse_time(event.occurred_at, "key custody occurred_at")
        if occurred > observed_at:
            raise DomainError("key custody event cannot follow as_of")
        due_at = event.due_at
        if event.event_type is KeyCustodyEventType.ISSUED:
            if due_at is None or parse_time(due_at, "key custody due_at") <= occurred:
                raise DomainError("issued key requires a due_at after issue time")
        elif due_at is not None:
            raise DomainError("returned key event cannot contain due_at")
        normalized.append(
            (KeyCustodyEvent(event_id, key_id, event.event_type, custodian, event.occurred_at, due_at), occurred)
        )
    normalized.sort(key=lambda row: (row[1], row[0].event_id))
    positions: dict[str, tuple[str, str, str]] = {}
    last_at: dict[str, datetime] = {}
    known_keys: set[str] = set()
    for event, occurred in normalized:
        known_keys.add(event.key_id)
        if occurred < last_at.get(event.key_id, occurred):
            raise DomainError(f"key custody chronology is invalid for {event.key_id}")
        last_at[event.key_id] = occurred
        current = positions.get(event.key_id)
        if event.event_type is KeyCustodyEventType.ISSUED:
            if current is not None:
                raise DomainError(f"clinic key {event.key_id} is already issued")
            if event.due_at is None:
                raise DomainError("issued key due_at is required")
            positions[event.key_id] = (event.custodian, event.occurred_at, event.due_at)
        else:
            if current is None:
                raise DomainError(f"clinic key {event.key_id} cannot be returned before issue")
            if current[0].casefold() != event.custodian.casefold():
                raise DomainError(f"clinic key {event.key_id} return custodian does not match")
            del positions[event.key_id]
    result: list[KeyCustodyPosition] = []
    for key_id in sorted(known_keys):
        current = positions.get(key_id)
        if current is None:
            result.append(KeyCustodyPosition(key_id, None, None, None, False))
        else:
            custodian, issued_at, due_at = current
            result.append(
                KeyCustodyPosition(key_id, custodian, issued_at, due_at, parse_time(due_at, "due_at") < observed_at)
            )
    return result
