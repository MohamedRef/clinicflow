"""Assess staff access-badge readiness for scheduled clinic areas."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class StaffAreaAssignment:
    staff_id: str
    area_id: str


@dataclass(frozen=True, slots=True)
class StaffBadgeGrant:
    staff_id: str
    area_id: str
    expires_day: int
    suspended: bool = False


@dataclass(frozen=True, slots=True)
class StaffBadgeFinding:
    staff_id: str
    missing_area_ids: tuple[str, ...]
    expired_area_ids: tuple[str, ...]
    suspended_area_ids: tuple[str, ...]
    ready: bool


def assess_staff_badges(
    assignments: list[StaffAreaAssignment], grants: list[StaffBadgeGrant], work_day: int
) -> list[StaffBadgeFinding]:
    """Require one current non-suspended grant for every assigned clinic area."""
    if work_day < 0:
        raise DomainError("badge work day cannot be negative")
    required: dict[str, set[str]] = {}
    for assignment in assignments:
        staff_id = clean_code(assignment.staff_id, "badge staff id")
        area_id = clean_code(assignment.area_id, "assigned area id")
        if area_id in required.setdefault(staff_id, set()):
            raise DomainError(f"duplicate staff area assignment: {staff_id}/{area_id}")
        required[staff_id].add(area_id)

    by_key: dict[tuple[str, str], StaffBadgeGrant] = {}
    for grant in grants:
        staff_id = clean_code(grant.staff_id, "badge grant staff id")
        area_id = clean_code(grant.area_id, "badge grant area id")
        key = (staff_id, area_id)
        if key in by_key:
            raise DomainError(f"duplicate staff badge grant: {staff_id}/{area_id}")
        if staff_id not in required or area_id not in required[staff_id] or grant.expires_day < 0:
            raise DomainError("staff badge grant must match an assignment and valid expiry")
        by_key[key] = grant

    findings: list[StaffBadgeFinding] = []
    for staff_id, areas in required.items():
        missing: list[str] = []
        expired: list[str] = []
        suspended: list[str] = []
        for area_id in areas:
            current = by_key.get((staff_id, area_id))
            if current is None:
                missing.append(area_id)
            elif current.suspended:
                suspended.append(area_id)
            elif current.expires_day < work_day:
                expired.append(area_id)
        findings.append(
            StaffBadgeFinding(
                staff_id,
                tuple(sorted(missing)),
                tuple(sorted(expired)),
                tuple(sorted(suspended)),
                not missing and not expired and not suspended,
            )
        )
    return sorted(findings, key=lambda item: (item.ready, item.staff_id))
