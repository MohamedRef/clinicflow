"""Assess non-clinical room utility readiness before scheduled use."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class RoomUtilityCheck:
    room_id: str
    utility: str
    required: bool
    available: bool
    backup_available: bool


@dataclass(frozen=True, slots=True)
class RoomUtilityFinding:
    room_id: str
    utility: str
    disposition: str


def assess_room_utilities(checks: list[RoomUtilityCheck]) -> list[RoomUtilityFinding]:
    """Return required room utilities that are unavailable or dependent on backup."""
    seen: set[tuple[str, str]] = set()
    findings: list[RoomUtilityFinding] = []
    for check in checks:
        room_id = clean_code(check.room_id, "room utility room id")
        utility = clean_code(check.utility, "room utility type").lower()
        key = (room_id, utility)
        if key in seen:
            raise DomainError(f"duplicate room utility check: {room_id}/{utility}")
        seen.add(key)
        if not check.required:
            continue
        if not check.available and not check.backup_available:
            findings.append(RoomUtilityFinding(room_id, utility, "unavailable"))
        elif not check.available:
            findings.append(RoomUtilityFinding(room_id, utility, "backup_only"))
    priority = {"unavailable": 0, "backup_only": 1}
    return sorted(findings, key=lambda item: (priority[item.disposition], item.room_id, item.utility))
