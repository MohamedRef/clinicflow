"""Prioritized repair planning for clinic room downtime."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import DomainError, clean_code, clean_codes, parse_time


@dataclass(frozen=True, slots=True)
class RoomDowntime:
    incident_id: str
    room_id: str
    detected_at: str
    restore_by: str
    repair_minutes: int
    required_skills: set[str]
    impacted_appointments: int


@dataclass(frozen=True, slots=True)
class RepairCrew:
    crew_id: str
    skills: set[str]
    available_from: str
    available_until: str
    maximum_jobs: int


@dataclass(frozen=True, slots=True)
class DowntimeRepairPlan:
    incident_id: str
    crew_id: str | None
    starts_at: str | None
    completes_at: str | None
    on_time: bool
    reason: str


def plan_room_downtime_repairs(incidents: list[RoomDowntime], crews: list[RepairCrew]) -> list[DowntimeRepairPlan]:
    """Allocate capable crews while preserving a deterministic repair queue."""
    crew_map: dict[str, tuple[RepairCrew, datetime, datetime]] = {}
    for crew in crews:
        crew_id = clean_code(crew.crew_id, "repair crew id")
        if crew_id in crew_map:
            raise DomainError(f"duplicate repair crew id: {crew_id}")
        start = parse_time(crew.available_from, "available_from")
        end = parse_time(crew.available_until, "available_until")
        if end <= start:
            raise DomainError("repair crew availability must have positive duration")
        if (
            isinstance(crew.maximum_jobs, bool)
            or not isinstance(crew.maximum_jobs, int)
            or not 1 <= crew.maximum_jobs <= 20
        ):
            raise DomainError("repair crew maximum_jobs must be from 1 through 20")
        normalized = RepairCrew(
            crew_id,
            clean_codes(crew.skills, "repair skill"),
            crew.available_from,
            crew.available_until,
            crew.maximum_jobs,
        )
        crew_map[crew_id] = (normalized, start, end)
    seen: set[str] = set()
    queue: list[tuple[RoomDowntime, datetime, datetime]] = []
    for incident in incidents:
        incident_id = clean_code(incident.incident_id, "downtime incident id")
        if incident_id in seen:
            raise DomainError(f"duplicate downtime incident id: {incident_id}")
        seen.add(incident_id)
        detected = parse_time(incident.detected_at, "detected_at")
        restore_by = parse_time(incident.restore_by, "restore_by")
        if restore_by <= detected:
            raise DomainError("downtime restore_by must follow detection")
        if (
            isinstance(incident.repair_minutes, bool)
            or not isinstance(incident.repair_minutes, int)
            or not 1 <= incident.repair_minutes <= 1_440
        ):
            raise DomainError("repair minutes must be from 1 through 1440")
        if (
            isinstance(incident.impacted_appointments, bool)
            or not isinstance(incident.impacted_appointments, int)
            or incident.impacted_appointments < 0
        ):
            raise DomainError("impacted appointments must be a non-negative integer")
        queue.append(
            (
                RoomDowntime(
                    incident_id,
                    clean_code(incident.room_id, "downtime room id"),
                    incident.detected_at,
                    incident.restore_by,
                    incident.repair_minutes,
                    clean_codes(incident.required_skills, "required repair skill"),
                    incident.impacted_appointments,
                ),
                detected,
                restore_by,
            )
        )
    availability = {crew_id: available_from for crew_id, (_, available_from, _) in crew_map.items()}
    jobs = {crew_id: 0 for crew_id in crew_map}
    plans: list[DowntimeRepairPlan] = []
    for incident, detected, restore_by in sorted(
        queue, key=lambda row: (-row[0].impacted_appointments, row[2], row[0].incident_id)
    ):
        candidates = []
        for crew_id, (crew, available_from, available_until) in crew_map.items():
            if jobs[crew_id] >= crew.maximum_jobs or not incident.required_skills <= crew.skills:
                continue
            start = max(detected, available_from, availability[crew_id])
            completion = start + timedelta(minutes=incident.repair_minutes)
            if completion <= available_until:
                candidates.append((completion > restore_by, completion, start, crew_id))
        if not candidates:
            plans.append(
                DowntimeRepairPlan(incident.incident_id, None, None, None, False, "no capable crew within availability")
            )
            continue
        late, completion, start, crew_id = min(candidates)
        availability[crew_id] = completion
        jobs[crew_id] += 1
        plans.append(
            DowntimeRepairPlan(
                incident.incident_id,
                crew_id,
                start.isoformat(),
                completion.isoformat(),
                not late,
                "deadline missed" if late else "repair scheduled",
            )
        )
    return plans
