"""Clinic scheduling, readiness, inventory reservation, and lifecycle rules."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any

from .models import (
    Appointment,
    AppointmentStatus,
    ClinicSnapshot,
    DomainError,
    InventoryItem,
    MaintenanceBlock,
    Room,
    StaffMember,
    assert_window,
    clean_code,
    clean_codes,
    clean_text,
    overlaps,
    parse_time,
)


class ClinicFlow:
    """Owns a consistent in-memory clinic operations snapshot."""

    def __init__(self, snapshot: ClinicSnapshot | None = None) -> None:
        self._state = deepcopy(snapshot) if snapshot is not None else ClinicSnapshot()

    def add_room(self, room_id: str, name: str, capabilities: set[str]) -> Room:
        room = Room.create(room_id, name, capabilities)
        if room.id in self._state.rooms:
            raise DomainError(f"room already exists: {room.id}")
        self._state.rooms[room.id] = room
        return deepcopy(room)

    def add_staff(self, staff_id: str, name: str, qualifications: set[str]) -> StaffMember:
        member = StaffMember.create(staff_id, name, qualifications)
        if member.id in self._state.staff:
            raise DomainError(f"staff member already exists: {member.id}")
        self._state.staff[member.id] = member
        return deepcopy(member)

    def add_inventory(self, sku: str, name: str, on_hand: int, reorder_level: int) -> InventoryItem:
        item = InventoryItem.create(sku, name, on_hand, reorder_level)
        if item.sku in self._state.inventory:
            raise DomainError(f"inventory item already exists: {item.sku}")
        self._state.inventory[item.sku] = item
        return deepcopy(item)

    def receive_inventory(self, sku: str, quantity: int) -> InventoryItem:
        item = self._inventory(sku)
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise DomainError("received quantity must be a positive integer")
        item.on_hand += quantity
        return deepcopy(item)

    def deactivate_room(self, room_id: str) -> Room:
        room = self._room(room_id)
        if any(
            row.room_id == room.id and row.status is AppointmentStatus.SCHEDULED
            for row in self._state.appointments.values()
        ):
            raise DomainError("cannot deactivate a room with scheduled appointments")
        room.active = False
        return deepcopy(room)

    def deactivate_staff(self, staff_id: str) -> StaffMember:
        member = self._staff(staff_id)
        if any(
            member.id in row.staff_ids and row.status is AppointmentStatus.SCHEDULED
            for row in self._state.appointments.values()
        ):
            raise DomainError("cannot deactivate staff with scheduled appointments")
        member.active = False
        return deepcopy(member)

    def block_room(
        self,
        block_id: str,
        room_id: str,
        starts_at: str,
        ends_at: str,
        reason: str,
    ) -> MaintenanceBlock:
        block = MaintenanceBlock.create(block_id, room_id, starts_at, ends_at, reason)
        self._room(block.room_id)
        if block.id in self._state.maintenance:
            raise DomainError(f"maintenance block already exists: {block.id}")
        if any(
            row.room_id == block.room_id
            and row.status is AppointmentStatus.SCHEDULED
            and overlaps(row.starts_at, row.ends_at, starts_at, ends_at)
            for row in self._state.appointments.values()
        ):
            raise DomainError("maintenance window overlaps a scheduled appointment")
        if any(
            row.room_id == block.room_id and overlaps(row.starts_at, row.ends_at, starts_at, ends_at)
            for row in self._state.maintenance.values()
        ):
            raise DomainError("maintenance window overlaps an existing block")
        self._state.maintenance[block.id] = block
        return deepcopy(block)

    def schedule(
        self,
        appointment_id: str,
        patient_reference: str,
        procedure: str,
        room_id: str,
        staff_ids: list[str],
        starts_at: str,
        ends_at: str,
        *,
        required_room_capabilities: set[str] | None = None,
        required_qualifications: set[str] | None = None,
        inventory_requirements: dict[str, int] | None = None,
    ) -> Appointment:
        normalized_id = clean_code(appointment_id, "appointment id")
        if normalized_id in self._state.appointments:
            raise DomainError(f"appointment already exists: {normalized_id}")
        assert_window(starts_at, ends_at)
        room = self._room(room_id)
        if not room.active:
            raise DomainError("room is inactive")
        capabilities = clean_codes(required_room_capabilities or set(), "room capability")
        missing_capabilities = capabilities - room.capabilities
        if missing_capabilities:
            raise DomainError(f"room lacks capabilities: {', '.join(sorted(missing_capabilities))}")
        normalized_staff_ids = [clean_code(value, "staff id") for value in staff_ids]
        if not normalized_staff_ids:
            raise DomainError("at least one staff member is required")
        if len(set(normalized_staff_ids)) != len(normalized_staff_ids):
            raise DomainError("staff ids must be unique")
        members = [self._staff(value) for value in normalized_staff_ids]
        if any(not member.active for member in members):
            raise DomainError("inactive staff cannot be scheduled")
        qualifications = clean_codes(required_qualifications or set(), "qualification")
        covered = set().union(*(member.qualifications for member in members))
        missing_qualifications = qualifications - covered
        if missing_qualifications:
            raise DomainError(f"staff lack qualifications: {', '.join(sorted(missing_qualifications))}")
        if self._room_busy(room.id, starts_at, ends_at):
            raise DomainError("room is unavailable for the requested window")
        for staff_id in normalized_staff_ids:
            if self._staff_busy(staff_id, starts_at, ends_at):
                raise DomainError(f"staff member is unavailable: {staff_id}")
        requirements = self._validate_requirements(inventory_requirements or {})
        for sku, quantity in requirements.items():
            if self._inventory(sku).available < quantity:
                raise DomainError(f"insufficient available inventory: {sku}")
        appointment = Appointment(
            id=normalized_id,
            patient_reference=clean_text(patient_reference, "patient reference", 120),
            procedure=clean_text(procedure, "procedure", 160),
            room_id=room.id,
            staff_ids=normalized_staff_ids,
            starts_at=starts_at,
            ends_at=ends_at,
            required_room_capabilities=capabilities,
            required_qualifications=qualifications,
            inventory_requirements=requirements,
        )
        for sku, quantity in requirements.items():
            self._state.inventory[sku].reserved += quantity
        self._state.appointments[appointment.id] = appointment
        return deepcopy(appointment)

    def cancel(self, appointment_id: str, reason: str, expected_version: int) -> Appointment:
        appointment = self._appointment(appointment_id)
        self._assert_mutable(appointment, expected_version)
        appointment.cancellation_reason = clean_text(reason, "cancellation reason", 500)
        appointment.status = AppointmentStatus.CANCELLED
        appointment.version += 1
        self._release_reservations(appointment)
        return deepcopy(appointment)

    def complete(self, appointment_id: str, expected_version: int) -> Appointment:
        appointment = self._appointment(appointment_id)
        self._assert_mutable(appointment, expected_version)
        appointment.status = AppointmentStatus.COMPLETED
        appointment.version += 1
        for sku, quantity in appointment.inventory_requirements.items():
            item = self._state.inventory[sku]
            item.reserved -= quantity
            item.on_hand -= quantity
        return deepcopy(appointment)

    def appointment(self, appointment_id: str) -> Appointment:
        return deepcopy(self._appointment(appointment_id))

    def appointments(self, status: AppointmentStatus | None = None) -> list[Appointment]:
        return [
            deepcopy(row)
            for row in sorted(
                self._state.appointments.values(), key=lambda item: (parse_time(item.starts_at, "starts_at"), item.id)
            )
            if status is None or row.status is status
        ]

    def readiness(self, appointment_id: str) -> dict[str, Any]:
        appointment = self._appointment(appointment_id)
        room = self._room(appointment.room_id)
        missing_inventory = {
            sku: quantity - self._inventory(sku).available - self._inventory(sku).reserved
            for sku, quantity in appointment.inventory_requirements.items()
            if self._inventory(sku).on_hand < quantity
        }
        return {
            "appointment_id": appointment.id,
            "status": appointment.status.value,
            "room_active": room.active,
            "staff_active": all(self._staff(staff_id).active for staff_id in appointment.staff_ids),
            "inventory_shortages": missing_inventory,
            "ready": appointment.status is AppointmentStatus.SCHEDULED
            and room.active
            and all(self._staff(staff_id).active for staff_id in appointment.staff_ids)
            and not missing_inventory,
        }

    def inventory_report(self) -> list[dict[str, Any]]:
        return [
            {
                "sku": item.sku,
                "name": item.name,
                "on_hand": item.on_hand,
                "reserved": item.reserved,
                "available": item.available,
                "below_reorder": item.available <= item.reorder_level,
            }
            for item in sorted(self._state.inventory.values(), key=lambda row: row.sku)
        ]

    def snapshot(self) -> ClinicSnapshot:
        return deepcopy(self._state)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "rooms": [self._plain(row) for row in sorted(self._state.rooms.values(), key=lambda item: item.id)],
            "staff": [self._plain(row) for row in sorted(self._state.staff.values(), key=lambda item: item.id)],
            "inventory": [
                self._plain(row) for row in sorted(self._state.inventory.values(), key=lambda item: item.sku)
            ],
            "appointments": [row.to_dict() for row in self.appointments()],
            "maintenance": [
                self._plain(row) for row in sorted(self._state.maintenance.values(), key=lambda item: item.id)
            ],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ClinicFlow:
        if value.get("schema_version") != 1:
            raise DomainError("unsupported clinic snapshot schema")
        try:
            for collection, key in (
                ("rooms", "id"),
                ("staff", "id"),
                ("inventory", "sku"),
                ("appointments", "id"),
                ("maintenance", "id"),
            ):
                rows = value[collection]
                if not isinstance(rows, list):
                    raise DomainError(f"snapshot {collection} must be a list")
                identifiers: set[str] = set()
                for row in rows:
                    if not isinstance(row, dict) or not isinstance(row.get(key), str):
                        raise DomainError(f"snapshot {collection} contains an invalid identity")
                    identifier = clean_code(row[key], f"snapshot {collection} identity")
                    if identifier in identifiers:
                        raise DomainError(f"duplicate snapshot {collection} identity: {identifier}")
                    if identifier != row[key]:
                        raise DomainError(f"snapshot {collection} identity must be canonical")
                    identifiers.add(identifier)
            snapshot = ClinicSnapshot(
                rooms={row["id"]: Room(**{**row, "capabilities": set(row["capabilities"])}) for row in value["rooms"]},
                staff={
                    row["id"]: StaffMember(**{**row, "qualifications": set(row["qualifications"])})
                    for row in value["staff"]
                },
                inventory={row["sku"]: InventoryItem(**row) for row in value["inventory"]},
                appointments={row["id"]: Appointment.from_dict(row) for row in value["appointments"]},
                maintenance={row["id"]: MaintenanceBlock(**row) for row in value["maintenance"]},
            )
        except (KeyError, TypeError, ValueError) as error:
            raise DomainError(f"invalid clinic snapshot: {error}") from error
        return cls(snapshot)

    def _room_busy(self, room_id: str, starts_at: str, ends_at: str) -> bool:
        appointments_busy = any(
            row.room_id == room_id
            and row.status is AppointmentStatus.SCHEDULED
            and overlaps(row.starts_at, row.ends_at, starts_at, ends_at)
            for row in self._state.appointments.values()
        )
        maintenance_busy = any(
            row.room_id == room_id and overlaps(row.starts_at, row.ends_at, starts_at, ends_at)
            for row in self._state.maintenance.values()
        )
        return appointments_busy or maintenance_busy

    def _staff_busy(self, staff_id: str, starts_at: str, ends_at: str) -> bool:
        return any(
            staff_id in row.staff_ids
            and row.status is AppointmentStatus.SCHEDULED
            and overlaps(row.starts_at, row.ends_at, starts_at, ends_at)
            for row in self._state.appointments.values()
        )

    def _validate_requirements(self, values: dict[str, int]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for raw_sku, quantity in values.items():
            sku = clean_code(raw_sku, "inventory sku")
            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
                raise DomainError("inventory requirements must be positive integers")
            if sku in normalized:
                raise DomainError(f"duplicate inventory requirement: {sku}")
            self._inventory(sku)
            normalized[sku] = quantity
        return normalized

    def _assert_mutable(self, appointment: Appointment, expected_version: int) -> None:
        if appointment.version != expected_version:
            raise DomainError(f"version conflict: expected {expected_version}, found {appointment.version}")
        if appointment.status is not AppointmentStatus.SCHEDULED:
            raise DomainError("only scheduled appointments can change")

    def _release_reservations(self, appointment: Appointment) -> None:
        for sku, quantity in appointment.inventory_requirements.items():
            self._state.inventory[sku].reserved -= quantity

    def _room(self, room_id: str) -> Room:
        normalized = clean_code(room_id, "room id")
        if normalized not in self._state.rooms:
            raise DomainError(f"room not found: {normalized}")
        return self._state.rooms[normalized]

    def _staff(self, staff_id: str) -> StaffMember:
        normalized = clean_code(staff_id, "staff id")
        if normalized not in self._state.staff:
            raise DomainError(f"staff member not found: {normalized}")
        return self._state.staff[normalized]

    def _inventory(self, sku: str) -> InventoryItem:
        normalized = clean_code(sku, "sku")
        if normalized not in self._state.inventory:
            raise DomainError(f"inventory item not found: {normalized}")
        return self._state.inventory[normalized]

    def _appointment(self, appointment_id: str) -> Appointment:
        normalized = clean_code(appointment_id, "appointment id")
        if normalized not in self._state.appointments:
            raise DomainError(f"appointment not found: {normalized}")
        return self._state.appointments[normalized]

    @staticmethod
    def _plain(value: Any) -> dict[str, Any]:
        result = asdict(value)
        for key, item in tuple(result.items()):
            if isinstance(item, set):
                result[key] = sorted(item)
        return result
