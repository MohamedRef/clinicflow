"""Assess manual reception continuity during system outages."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class ReceptionContinuityRequirement:
    clinic_id: str
    minimum_paper_forms: int
    minimum_offline_devices: int
    escalation_contact_required: bool


@dataclass(frozen=True, slots=True)
class ReceptionContinuityCheck:
    clinic_id: str
    paper_forms: int
    offline_devices: int
    escalation_contact_verified: bool
    last_rehearsed_day: int


@dataclass(frozen=True, slots=True)
class ReceptionContinuityFinding:
    clinic_id: str
    form_shortfall: int
    device_shortfall: int
    contact_ready: bool
    rehearsal_current: bool
    ready: bool


def assess_reception_continuity(
    requirements: list[ReceptionContinuityRequirement],
    checks: list[ReceptionContinuityCheck],
    current_day: int,
    maximum_rehearsal_age_days: int,
) -> list[ReceptionContinuityFinding]:
    """Check supplies, offline devices, escalation, and rehearsal currency."""
    if current_day < 0 or maximum_rehearsal_age_days < 1:
        raise DomainError("reception continuity timing is invalid")
    required: dict[str, ReceptionContinuityRequirement] = {}
    for requirement in requirements:
        clinic_id = clean_code(requirement.clinic_id, "continuity clinic id")
        if clinic_id in required:
            raise DomainError(f"duplicate continuity requirement: {clinic_id}")
        if requirement.minimum_paper_forms < 0 or requirement.minimum_offline_devices < 0:
            raise DomainError("reception continuity requirement is invalid")
        required[clinic_id] = ReceptionContinuityRequirement(
            clinic_id,
            requirement.minimum_paper_forms,
            requirement.minimum_offline_devices,
            requirement.escalation_contact_required,
        )
    seen: set[str] = set()
    findings: list[ReceptionContinuityFinding] = []
    for check in checks:
        clinic_id = clean_code(check.clinic_id, "continuity check clinic id")
        matched = required.get(clinic_id)
        if matched is None or clinic_id in seen:
            raise DomainError("reception continuity check is unknown or duplicated")
        if (
            check.paper_forms < 0
            or check.offline_devices < 0
            or check.last_rehearsed_day < 0
            or check.last_rehearsed_day > current_day
        ):
            raise DomainError("reception continuity check is invalid")
        seen.add(clinic_id)
        form_shortfall = max(0, matched.minimum_paper_forms - check.paper_forms)
        device_shortfall = max(0, matched.minimum_offline_devices - check.offline_devices)
        contact_ready = not matched.escalation_contact_required or check.escalation_contact_verified
        rehearsal_current = current_day - check.last_rehearsed_day <= maximum_rehearsal_age_days
        findings.append(
            ReceptionContinuityFinding(
                clinic_id,
                form_shortfall,
                device_shortfall,
                contact_ready,
                rehearsal_current,
                form_shortfall == 0 and device_shortfall == 0 and contact_ready and rehearsal_current,
            )
        )
    if seen != set(required):
        raise DomainError("every reception continuity requirement needs a check")
    return sorted(findings, key=lambda item: (item.ready, item.clinic_id))
