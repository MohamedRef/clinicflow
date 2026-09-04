"""Assess non-clinical appointment packets before reception handoff."""

from dataclasses import dataclass

from clinicflow.models import DomainError, clean_text


@dataclass(frozen=True, slots=True)
class AppointmentPacket:
    appointment_id: str
    required_documents: tuple[str, ...]
    received_documents: tuple[str, ...]
    contact_confirmed: bool
    room_assignment: str | None


@dataclass(frozen=True, slots=True)
class AppointmentPacketFinding:
    appointment_id: str
    missing_documents: tuple[str, ...]
    defects: tuple[str, ...]
    state: str


def assess_appointment_packets(packets: list[AppointmentPacket]) -> list[AppointmentPacketFinding]:
    """Return blocked, incomplete, and ready reception packets."""
    seen: set[str] = set()
    findings: list[AppointmentPacketFinding] = []
    for packet in packets:
        appointment_id = clean_text(packet.appointment_id, "appointment packet", 120)
        key = appointment_id.casefold()
        if key in seen:
            raise DomainError("duplicate appointment packet")
        seen.add(key)
        required = _documents(packet.required_documents, "required appointment document")
        received = _documents(packet.received_documents, "received appointment document")
        if not required:
            raise DomainError("appointment packet requires at least one document")
        unexpected = received - required
        if unexpected:
            raise DomainError("appointment packet contains unexpected documents")
        missing = tuple(sorted(required - received))
        defects: list[str] = []
        if missing:
            defects.append("documents_missing")
        if not packet.contact_confirmed:
            defects.append("contact_unconfirmed")
        if packet.room_assignment is None or not packet.room_assignment.strip():
            defects.append("room_unassigned")
        if "room_unassigned" in defects or "contact_unconfirmed" in defects:
            state = "blocked"
        elif missing:
            state = "incomplete"
        else:
            state = "ready"
        findings.append(AppointmentPacketFinding(appointment_id, missing, tuple(defects), state))
    order = {"blocked": 0, "incomplete": 1, "ready": 2}
    return sorted(findings, key=lambda row: (order[row.state], -len(row.missing_documents), row.appointment_id))


def _documents(values: tuple[str, ...], field: str) -> set[str]:
    normalized = {clean_text(value, field, 80).casefold() for value in values}
    if len(normalized) != len(values):
        raise DomainError(f"{field} values must be unique")
    return normalized
