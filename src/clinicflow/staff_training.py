"""Match operational duties to current staff training evidence."""

from dataclasses import dataclass
from datetime import datetime

from .models import DomainError, clean_code, clean_text, parse_time


@dataclass(frozen=True, slots=True)
class StaffTrainingRecord:
    staff_id: str
    course: str
    completed_at: str
    expires_at: str


@dataclass(frozen=True, slots=True)
class StaffDutyRequirement:
    duty_id: str
    staff_id: str
    course: str
    starts_at: str


@dataclass(frozen=True, slots=True)
class StaffTrainingFinding:
    duty_id: str
    staff_id: str
    ready: bool
    reason: str
    expires_at: str | None


def assess_staff_training(
    records: list[StaffTrainingRecord], duties: list[StaffDutyRequirement]
) -> list[StaffTrainingFinding]:
    """Require training to be complete and unexpired when a duty starts."""
    evidence: dict[tuple[str, str], tuple[str, datetime, datetime]] = {}
    for record in records:
        staff_id = clean_code(record.staff_id, "training staff id")
        course = clean_text(record.course, "training course", 100)
        key = (staff_id.casefold(), course.casefold())
        if key in evidence:
            raise DomainError(f"duplicate staff training record: {staff_id} and {course}")
        completed = parse_time(record.completed_at, "completed_at")
        expires = parse_time(record.expires_at, "expires_at")
        if expires <= completed:
            raise DomainError("staff training expiry must follow completion")
        evidence[key] = (record.expires_at, completed, expires)
    seen: set[str] = set()
    findings: list[StaffTrainingFinding] = []
    for duty in duties:
        duty_id = clean_code(duty.duty_id, "duty id")
        if duty_id.casefold() in seen:
            raise DomainError(f"duplicate staff duty requirement: {duty_id}")
        seen.add(duty_id.casefold())
        staff_id = clean_code(duty.staff_id, "duty staff id")
        course = clean_text(duty.course, "required course", 100)
        starts = parse_time(duty.starts_at, "starts_at")
        evidence_row = evidence.get((staff_id.casefold(), course.casefold()))
        if evidence_row is None:
            findings.append(StaffTrainingFinding(duty_id, staff_id, False, "required training is missing", None))
            continue
        expires_text, completed, expires = evidence_row
        if starts < completed:
            raise DomainError("staff duty cannot predate training completion")
        ready = starts <= expires
        reason = "training current" if ready else "training expired"
        findings.append(StaffTrainingFinding(duty_id, staff_id, ready, reason, expires_text))
    return sorted(findings, key=lambda row: (row.ready, row.duty_id))
