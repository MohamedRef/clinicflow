"""Detect reception queue order and wait-time fairness exceptions."""

from dataclasses import dataclass
from datetime import datetime

from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class ReceptionQueueVisit:
    visit_id: str
    clinic_id: str
    arrived_at: str
    served_at: str | None
    priority: int = 0


@dataclass(frozen=True, slots=True)
class ReceptionFairnessPolicy:
    clinic_id: str
    maximum_wait_minutes: int
    maximum_overtakes: int


@dataclass(frozen=True, slots=True)
class ReceptionFairnessFinding:
    visit_id: str
    wait_minutes: int | None
    overtaken_by: tuple[str, ...]
    excessive_wait: bool


def assess_reception_fairness(
    visits: list[ReceptionQueueVisit], policies: list[ReceptionFairnessPolicy]
) -> list[ReceptionFairnessFinding]:
    """Report visits with excessive waits or too many same-priority overtakes."""
    configured: dict[str, ReceptionFairnessPolicy] = {}
    for policy in policies:
        clinic_id = clean_code(policy.clinic_id, "fairness clinic id")
        if clinic_id in configured:
            raise DomainError(f"duplicate reception fairness policy: {clinic_id}")
        if policy.maximum_wait_minutes < 1 or policy.maximum_overtakes < 0:
            raise DomainError("reception fairness limits are invalid")
        configured[clinic_id] = policy

    normalized: list[tuple[ReceptionQueueVisit, datetime, datetime | None]] = []
    seen: set[str] = set()
    for visit in visits:
        visit_id = clean_code(visit.visit_id, "reception visit id")
        clinic_id = clean_code(visit.clinic_id, "reception visit clinic")
        if visit_id in seen:
            raise DomainError(f"duplicate reception visit: {visit_id}")
        if clinic_id not in configured:
            raise DomainError(f"reception fairness policy missing: {clinic_id}")
        if not isinstance(visit.priority, int) or isinstance(visit.priority, bool) or visit.priority < 0:
            raise DomainError("reception priority must be a non-negative integer")
        arrival = parse_time(visit.arrived_at, "reception arrived_at")
        served = parse_time(visit.served_at, "reception served_at") if visit.served_at else None
        if served is not None and served < arrival:
            raise DomainError("reception service cannot precede arrival")
        seen.add(visit_id)
        normalized.append((visit, arrival, served))

    findings: list[ReceptionFairnessFinding] = []
    for visit, arrival, served in normalized:
        policy = configured[visit.clinic_id.strip()]
        overtaken = tuple(
            sorted(
                other.visit_id
                for other, other_arrival, other_served in normalized
                if other.clinic_id.strip() == visit.clinic_id.strip()
                and other.priority == visit.priority
                and other_arrival > arrival
                and other_served is not None
                and (served is None or other_served < served)
            )
        )
        wait_minutes = int((served - arrival).total_seconds() // 60) if served else None
        excessive_wait = wait_minutes is None or wait_minutes > policy.maximum_wait_minutes
        if excessive_wait or len(overtaken) > policy.maximum_overtakes:
            findings.append(ReceptionFairnessFinding(visit.visit_id, wait_minutes, overtaken, excessive_wait))
    return sorted(findings, key=lambda item: (not item.excessive_wait, -(item.wait_minutes or 0), item.visit_id))
