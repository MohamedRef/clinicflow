"""Verify reception queue signage against active service lanes."""

from dataclasses import dataclass

from clinicflow.models import DomainError


@dataclass(frozen=True, slots=True)
class ReceptionLane:
    lane_id: str
    service_name: str
    open: bool


@dataclass(frozen=True, slots=True)
class QueueSign:
    lane_id: str
    displayed_service: str
    visible: bool


@dataclass(frozen=True, slots=True)
class QueueSignFinding:
    lane_id: str
    state: str


def assess_reception_queue_signage(lanes: list[ReceptionLane], signs: list[QueueSign]) -> list[QueueSignFinding]:
    """Flag missing, stale, or unexpectedly visible reception signs."""
    configured: dict[str, ReceptionLane] = {}
    for lane in lanes:
        lane_id = lane.lane_id.strip()
        if not lane_id or not lane.service_name.strip() or lane_id.casefold() in configured:
            raise DomainError("invalid or duplicate reception lane")
        configured[lane_id.casefold()] = lane
    observed: dict[str, QueueSign] = {}
    for sign in signs:
        key = sign.lane_id.strip().casefold()
        if key not in configured or key in observed:
            raise DomainError("unexpected or duplicate reception sign")
        observed[key] = sign
    findings: list[QueueSignFinding] = []
    for key, lane in configured.items():
        matched_sign = observed.get(key)
        state = (
            "missing"
            if lane.open and (matched_sign is None or not matched_sign.visible)
            else "stale"
            if lane.open
            and matched_sign
            and matched_sign.displayed_service.strip().casefold() != lane.service_name.strip().casefold()
            else "hide"
            if not lane.open and matched_sign and matched_sign.visible
            else "ready"
        )
        findings.append(QueueSignFinding(lane.lane_id.strip(), state))
    order = {"missing": 0, "stale": 1, "hide": 2, "ready": 3}
    return sorted(findings, key=lambda row: (order[row.state], row.lane_id))
