"""Room outage impact, relocation, repair, and return-to-service coordination."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum


class OutageCause(StrEnum):
    UTILITIES = "utilities"
    CLEANING = "cleaning"
    EQUIPMENT = "equipment"
    ACCESS = "access"
    SAFETY = "safety"
    BUILDING_WORK = "building_work"


class OutageState(StrEnum):
    OPEN = "open"
    CONTAINED = "contained"
    REPAIRING = "repairing"
    VERIFYING = "verifying"
    RESTORED = "restored"


@dataclass(frozen=True, slots=True)
class RoomOutage:
    outage_id: str
    room_id: str
    site_id: str
    cause: OutageCause
    reported_at: datetime
    reported_by: str
    expected_restore_at: datetime
    state: OutageState = OutageState.OPEN
    affected_appointment_ids: tuple[str, ...] = ()
    containment_note: str = ""
    restored_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RelocationOption:
    room_id: str
    site_id: str
    available_from: datetime
    available_until: datetime
    capabilities: tuple[str, ...]
    travel_minutes: int


@dataclass(frozen=True, slots=True)
class AppointmentImpact:
    appointment_id: str
    starts_at: datetime
    ends_at: datetime
    required_capabilities: tuple[str, ...]
    mobility_sensitive: bool
    assigned_room_id: str | None = None


@dataclass(frozen=True, slots=True)
class RelocationDecision:
    appointment_id: str
    outage_id: str
    room_id: str | None
    ready: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RestorationCheck:
    check_id: str
    outage_id: str
    check_kind: str
    checked_at: datetime
    checked_by: str
    passed: bool
    evidence_id: str


def _text(value: str, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field} is required")
    return normalized


def _instant(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _unique(values: Iterable[str], field: str) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _text(value, field)
        key = normalized.casefold()
        if key in seen:
            raise ValueError(f"duplicate {field}: {normalized}")
        seen.add(key)
        result.append(normalized)
    return tuple(result)


class RoomOutageBoard:
    """Protect appointments while rooms are unavailable and gate restoration."""

    def __init__(self, outages: Iterable[RoomOutage] = ()) -> None:
        self._outages: dict[str, RoomOutage] = {}
        self._rooms: dict[str, str] = {}
        self._checks: dict[str, RestorationCheck] = {}
        self._relocations: dict[str, RelocationDecision] = {}
        for outage in outages:
            self.open_outage(outage)

    def _normalize_outage(self, outage: RoomOutage) -> RoomOutage:
        reported_at = _instant(outage.reported_at, "outage report")
        expected = _instant(outage.expected_restore_at, "expected restoration")
        if expected <= reported_at:
            raise ValueError("expected restoration must follow outage report")
        restored = None if outage.restored_at is None else _instant(outage.restored_at, "restored at")
        if restored is not None and restored < reported_at:
            raise ValueError("restoration cannot predate outage")
        return RoomOutage(
            outage_id=_text(outage.outage_id, "outage id"),
            room_id=_text(outage.room_id, "room id"),
            site_id=_text(outage.site_id, "site id").casefold(),
            cause=outage.cause,
            reported_at=reported_at,
            reported_by=_text(outage.reported_by, "outage reporter"),
            expected_restore_at=expected,
            state=outage.state,
            affected_appointment_ids=_unique(outage.affected_appointment_ids, "appointment id"),
            containment_note=" ".join(outage.containment_note.split()),
            restored_at=restored,
        )

    def open_outage(self, outage: RoomOutage) -> RoomOutage:
        if outage.state is not OutageState.OPEN or outage.restored_at is not None:
            raise ValueError("new room outages must start open")
        normalized = self._normalize_outage(outage)
        key = normalized.outage_id.casefold()
        room_key = normalized.room_id.casefold()
        if key in self._outages:
            raise ValueError(f"duplicate room outage: {normalized.outage_id}")
        if room_key in self._rooms:
            raise ValueError(f"room already has active outage: {normalized.room_id}")
        self._outages[key] = normalized
        self._rooms[room_key] = normalized.outage_id
        return normalized

    def add_impacts(self, outage_id: str, appointment_ids: Iterable[str]) -> RoomOutage:
        key, outage = self._outage(outage_id)
        if outage.state is OutageState.RESTORED:
            raise ValueError("restored outages cannot receive impacts")
        merged = _unique((*outage.affected_appointment_ids, *appointment_ids), "appointment id")
        updated = replace(outage, affected_appointment_ids=merged)
        self._outages[key] = updated
        return updated

    def contain(self, outage_id: str, contained_at: datetime, note: str) -> RoomOutage:
        key, outage = self._outage(outage_id)
        contained = _instant(contained_at, "contained at")
        if outage.state is not OutageState.OPEN or contained < outage.reported_at:
            raise ValueError("only open outages can be contained after reporting")
        updated = replace(outage, state=OutageState.CONTAINED, containment_note=_text(note, "containment note"))
        self._outages[key] = updated
        return updated

    def start_repair(self, outage_id: str, started_at: datetime) -> RoomOutage:
        key, outage = self._outage(outage_id)
        started = _instant(started_at, "repair start")
        if outage.state is not OutageState.CONTAINED or started < outage.reported_at:
            raise ValueError("repair requires contained outage")
        updated = replace(outage, state=OutageState.REPAIRING)
        self._outages[key] = updated
        return updated

    def plan_relocations(
        self,
        outage_id: str,
        impacts: Iterable[AppointmentImpact],
        options: Iterable[RelocationOption],
    ) -> tuple[RelocationDecision, ...]:
        _, outage = self._outage(outage_id)
        option_list = [self._normalize_option(option) for option in options]
        used: set[str] = set()
        decisions: list[RelocationDecision] = []
        for impact in sorted(impacts, key=lambda item: (item.starts_at, item.appointment_id)):
            normalized = self._normalize_impact(impact)
            if normalized.appointment_id not in outage.affected_appointment_ids:
                raise ValueError(f"appointment is not registered on outage: {normalized.appointment_id}")
            candidates = [
                option
                for option in option_list
                if option.room_id.casefold() not in used
                and option.site_id == outage.site_id
                and option.available_from <= normalized.starts_at
                and option.available_until >= normalized.ends_at
                and set(normalized.required_capabilities) <= set(option.capabilities)
                and (not normalized.mobility_sensitive or option.travel_minutes <= 10)
            ]
            candidates.sort(key=lambda item: (item.travel_minutes, len(item.capabilities), item.room_id))
            selected = candidates[0] if candidates else None
            blockers: list[str] = []
            if selected is None:
                blockers.append("no suitable relocation room")
            else:
                used.add(selected.room_id.casefold())
            decision = RelocationDecision(
                appointment_id=normalized.appointment_id,
                outage_id=outage.outage_id,
                room_id=None if selected is None else selected.room_id,
                ready=selected is not None,
                blockers=tuple(blockers),
            )
            self._relocations[f"{outage.outage_id.casefold()}:{normalized.appointment_id.casefold()}"] = decision
            decisions.append(decision)
        return tuple(decisions)

    def _normalize_option(self, option: RelocationOption) -> RelocationOption:
        available_from = _instant(option.available_from, "room availability start")
        available_until = _instant(option.available_until, "room availability end")
        if available_until <= available_from or option.travel_minutes < 0:
            raise ValueError("relocation option availability is invalid")
        return RelocationOption(
            room_id=_text(option.room_id, "relocation room id"),
            site_id=_text(option.site_id, "relocation site id").casefold(),
            available_from=available_from,
            available_until=available_until,
            capabilities=_unique(option.capabilities, "room capability"),
            travel_minutes=option.travel_minutes,
        )

    def _normalize_impact(self, impact: AppointmentImpact) -> AppointmentImpact:
        starts_at = _instant(impact.starts_at, "appointment start")
        ends_at = _instant(impact.ends_at, "appointment end")
        if ends_at <= starts_at:
            raise ValueError("appointment end must follow start")
        return AppointmentImpact(
            appointment_id=_text(impact.appointment_id, "appointment id"),
            starts_at=starts_at,
            ends_at=ends_at,
            required_capabilities=_unique(impact.required_capabilities, "required capability"),
            mobility_sensitive=impact.mobility_sensitive,
            assigned_room_id=impact.assigned_room_id,
        )

    def record_check(self, check: RestorationCheck) -> RestorationCheck:
        key, outage = self._outage(check.outage_id)
        if outage.state not in {OutageState.REPAIRING, OutageState.VERIFYING}:
            raise ValueError("restoration checks require active repair")
        check_id = _text(check.check_id, "restoration check id")
        if check_id.casefold() in self._checks:
            raise ValueError(f"duplicate restoration check: {check_id}")
        checked_at = _instant(check.checked_at, "restoration check time")
        if checked_at < outage.reported_at:
            raise ValueError("restoration check cannot predate outage")
        normalized = RestorationCheck(
            check_id=check_id,
            outage_id=outage.outage_id,
            check_kind=_text(check.check_kind, "restoration check kind").casefold(),
            checked_at=checked_at,
            checked_by=_text(check.checked_by, "restoration checker"),
            passed=check.passed,
            evidence_id=_text(check.evidence_id, "restoration evidence id"),
        )
        self._checks[check_id.casefold()] = normalized
        self._outages[key] = replace(outage, state=OutageState.VERIFYING)
        return normalized

    def restoration_readiness(
        self, outage_id: str, required_check_kinds: Iterable[str]
    ) -> tuple[bool, tuple[str, ...]]:
        _, outage = self._outage(outage_id)
        required = _unique(required_check_kinds, "required check kind")
        latest: dict[str, RestorationCheck] = {}
        for check in self._checks.values():
            if check.outage_id.casefold() != outage.outage_id.casefold():
                continue
            current = latest.get(check.check_kind)
            if current is None or check.checked_at > current.checked_at:
                latest[check.check_kind] = check
        blockers: list[str] = []
        for kind in required:
            latest_check = latest.get(kind.casefold())
            if latest_check is None:
                blockers.append(f"missing restoration check: {kind}")
            elif not latest_check.passed:
                blockers.append(f"failed restoration check: {kind}")
        if any(
            not decision.ready
            for key, decision in self._relocations.items()
            if key.startswith(outage.outage_id.casefold() + ":")
        ):
            blockers.append("appointment relocation remains unresolved")
        return not blockers, tuple(blockers)

    def restore(
        self,
        outage_id: str,
        restored_at: datetime,
        required_check_kinds: Iterable[str],
    ) -> RoomOutage:
        key, outage = self._outage(outage_id)
        restored = _instant(restored_at, "restored at")
        ready, blockers = self.restoration_readiness(outage_id, required_check_kinds)
        if not ready:
            raise ValueError("room is not ready for restoration: " + "; ".join(blockers))
        if restored < outage.reported_at:
            raise ValueError("restoration cannot predate outage")
        updated = replace(outage, state=OutageState.RESTORED, restored_at=restored)
        self._outages[key] = updated
        del self._rooms[outage.room_id.casefold()]
        return updated

    def overdue(self, as_of: datetime) -> tuple[RoomOutage, ...]:
        now = _instant(as_of, "as of")
        result = [
            outage
            for outage in self._outages.values()
            if outage.state is not OutageState.RESTORED and outage.expected_restore_at < now
        ]
        result.sort(key=lambda item: (item.expected_restore_at, item.outage_id))
        return tuple(result)

    def _outage(self, outage_id: str) -> tuple[str, RoomOutage]:
        normalized = _text(outage_id, "outage id")
        key = normalized.casefold()
        try:
            return key, self._outages[key]
        except KeyError as exc:
            raise KeyError(f"unknown room outage: {normalized}") from exc
