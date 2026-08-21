"""Validated domain records for non-clinical clinic operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class DomainError(ValueError):
    """Raised when an operation violates a ClinicFlow invariant."""


def clean_text(value: str, field_name: str, maximum: int = 160) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise DomainError(f"{field_name} is required")
    if len(normalized) > maximum:
        raise DomainError(f"{field_name} must be at most {maximum} characters")
    return normalized


def clean_code(value: str, field_name: str) -> str:
    normalized = clean_text(value, field_name, 80).lower()
    if not all(character.isalnum() or character in {"-", "_"} for character in normalized):
        raise DomainError(f"{field_name} may contain only letters, numbers, hyphens, and underscores")
    return normalized


def clean_codes(values: set[str] | list[str], field_name: str) -> set[str]:
    return {clean_code(value, field_name) for value in values}


def parse_time(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise DomainError(f"{field_name} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DomainError(f"{field_name} must include a timezone")
    return parsed


def assert_window(starts_at: str, ends_at: str) -> None:
    if parse_time(ends_at, "ends_at") <= parse_time(starts_at, "starts_at"):
        raise DomainError("ends_at must be after starts_at")


def overlaps(left_start: str, left_end: str, right_start: str, right_end: str) -> bool:
    return parse_time(left_start, "starts_at") < parse_time(right_end, "ends_at") and parse_time(
        right_start, "starts_at"
    ) < parse_time(left_end, "ends_at")


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Room:
    id: str
    name: str
    capabilities: set[str]
    active: bool = True

    @classmethod
    def create(cls, room_id: str, name: str, capabilities: set[str]) -> Room:
        return cls(
            clean_code(room_id, "room id"), clean_text(name, "room name"), clean_codes(capabilities, "capability")
        )


@dataclass(slots=True)
class StaffMember:
    id: str
    name: str
    qualifications: set[str]
    active: bool = True

    @classmethod
    def create(cls, staff_id: str, name: str, qualifications: set[str]) -> StaffMember:
        return cls(
            clean_code(staff_id, "staff id"),
            clean_text(name, "staff name"),
            clean_codes(qualifications, "qualification"),
        )


@dataclass(slots=True)
class InventoryItem:
    sku: str
    name: str
    on_hand: int
    reserved: int
    reorder_level: int

    @classmethod
    def create(cls, sku: str, name: str, on_hand: int, reorder_level: int) -> InventoryItem:
        if not isinstance(on_hand, int) or on_hand < 0:
            raise DomainError("on_hand must be a non-negative integer")
        if not isinstance(reorder_level, int) or reorder_level < 0:
            raise DomainError("reorder_level must be a non-negative integer")
        return cls(clean_code(sku, "sku"), clean_text(name, "inventory name"), on_hand, 0, reorder_level)

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved


@dataclass(slots=True)
class MaintenanceBlock:
    id: str
    room_id: str
    starts_at: str
    ends_at: str
    reason: str

    @classmethod
    def create(cls, block_id: str, room_id: str, starts_at: str, ends_at: str, reason: str) -> MaintenanceBlock:
        assert_window(starts_at, ends_at)
        return cls(
            clean_code(block_id, "maintenance block id"),
            clean_code(room_id, "room id"),
            starts_at,
            ends_at,
            clean_text(reason, "maintenance reason", 500),
        )


@dataclass(slots=True)
class Appointment:
    id: str
    patient_reference: str
    procedure: str
    room_id: str
    staff_ids: list[str]
    starts_at: str
    ends_at: str
    required_room_capabilities: set[str]
    required_qualifications: set[str]
    inventory_requirements: dict[str, int]
    status: AppointmentStatus = AppointmentStatus.SCHEDULED
    version: int = 1
    cancellation_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        result["required_room_capabilities"] = sorted(self.required_room_capabilities)
        result["required_qualifications"] = sorted(self.required_qualifications)
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Appointment:
        return cls(
            id=str(value["id"]),
            patient_reference=str(value["patient_reference"]),
            procedure=str(value["procedure"]),
            room_id=str(value["room_id"]),
            staff_ids=[str(item) for item in value["staff_ids"]],
            starts_at=str(value["starts_at"]),
            ends_at=str(value["ends_at"]),
            required_room_capabilities={str(item) for item in value["required_room_capabilities"]},
            required_qualifications={str(item) for item in value["required_qualifications"]},
            inventory_requirements={str(key): int(amount) for key, amount in value["inventory_requirements"].items()},
            status=AppointmentStatus(str(value["status"])),
            version=int(value["version"]),
            cancellation_reason=str(value.get("cancellation_reason", "")),
        )


@dataclass(slots=True)
class ClinicSnapshot:
    rooms: dict[str, Room] = field(default_factory=dict)
    staff: dict[str, StaffMember] = field(default_factory=dict)
    inventory: dict[str, InventoryItem] = field(default_factory=dict)
    appointments: dict[str, Appointment] = field(default_factory=dict)
    maintenance: dict[str, MaintenanceBlock] = field(default_factory=dict)
