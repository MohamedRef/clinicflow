"""Match released no-show slots to eligible waiting appointments."""

from dataclasses import dataclass

from .models import DomainError, clean_code


@dataclass(frozen=True, slots=True)
class ReleasedNoShowSlot:
    slot_id: str
    clinic_id: str
    room_type: str
    start_minute: int
    end_minute: int


@dataclass(frozen=True, slots=True)
class NoShowWaitlistCandidate:
    appointment_id: str
    clinic_id: str
    acceptable_room_types: tuple[str, ...]
    duration_minutes: int
    can_arrive_by_minute: int
    priority: int


@dataclass(frozen=True, slots=True)
class NoShowRecoveryMatch:
    slot_id: str
    appointment_id: str | None
    recovered_minutes: int


def recover_no_show_capacity(
    slots: list[ReleasedNoShowSlot],
    candidates: list[NoShowWaitlistCandidate],
) -> list[NoShowRecoveryMatch]:
    """Fill released slots by priority while preserving clinic and room compatibility."""
    normalized_slots: list[ReleasedNoShowSlot] = []
    slot_ids: set[str] = set()
    for slot in slots:
        slot_id = clean_code(slot.slot_id, "released no-show slot id")
        clinic_id = clean_code(slot.clinic_id, "no-show slot clinic id")
        room_type = clean_code(slot.room_type, "no-show room type")
        if slot_id in slot_ids:
            raise DomainError(f"duplicate released no-show slot: {slot_id}")
        if slot.start_minute < 0 or slot.end_minute <= slot.start_minute:
            raise DomainError("released no-show slot has invalid timing")
        slot_ids.add(slot_id)
        normalized_slots.append(
            ReleasedNoShowSlot(
                slot_id,
                clinic_id,
                room_type,
                slot.start_minute,
                slot.end_minute,
            )
        )

    normalized_candidates: list[NoShowWaitlistCandidate] = []
    appointment_ids: set[str] = set()
    for candidate in candidates:
        appointment_id = clean_code(candidate.appointment_id, "waitlist appointment id")
        clinic_id = clean_code(candidate.clinic_id, "waitlist clinic id")
        room_types = tuple(
            sorted({clean_code(room_type, "acceptable room type") for room_type in candidate.acceptable_room_types})
        )
        if appointment_id in appointment_ids:
            raise DomainError(f"duplicate no-show waitlist appointment: {appointment_id}")
        if (
            not room_types
            or candidate.duration_minutes < 1
            or candidate.can_arrive_by_minute < 0
            or candidate.priority < 0
        ):
            raise DomainError("no-show waitlist candidate has invalid eligibility")
        appointment_ids.add(appointment_id)
        normalized_candidates.append(
            NoShowWaitlistCandidate(
                appointment_id,
                clinic_id,
                room_types,
                candidate.duration_minutes,
                candidate.can_arrive_by_minute,
                candidate.priority,
            )
        )

    used: set[str] = set()
    matches: list[NoShowRecoveryMatch] = []
    for slot in sorted(normalized_slots, key=lambda item: (item.start_minute, item.slot_id)):
        slot_minutes = slot.end_minute - slot.start_minute
        eligible = [
            candidate
            for candidate in normalized_candidates
            if candidate.appointment_id not in used
            and candidate.clinic_id == slot.clinic_id
            and slot.room_type in candidate.acceptable_room_types
            and candidate.duration_minutes <= slot_minutes
            and candidate.can_arrive_by_minute <= slot.start_minute
        ]
        if not eligible:
            matches.append(NoShowRecoveryMatch(slot.slot_id, None, 0))
            continue
        selected = min(
            eligible,
            key=lambda item: (
                -item.priority,
                item.can_arrive_by_minute,
                item.appointment_id,
            ),
        )
        used.add(selected.appointment_id)
        matches.append(
            NoShowRecoveryMatch(
                slot.slot_id,
                selected.appointment_id,
                selected.duration_minutes,
            )
        )
    return matches
