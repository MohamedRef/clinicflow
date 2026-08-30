"""Shared non-clinical equipment loan allocation."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class LoanEquipment:
    asset_id: str
    category: str
    available_from: str
    available_until: str
    inspected_at: str


@dataclass(frozen=True, slots=True)
class EquipmentLoanRequest:
    request_id: str
    appointment_id: str
    category: str
    starts_at: str
    ends_at: str
    priority: int


@dataclass(frozen=True, slots=True)
class EquipmentLoanAssignment:
    request_id: str
    asset_id: str | None
    assigned: bool
    reason: str


def allocate_equipment_loans(
    requests: list[EquipmentLoanRequest],
    equipment: list[LoanEquipment],
    assessed_at: str,
    inspection_maximum_age_days: int = 30,
) -> list[EquipmentLoanAssignment]:
    """Allocate inspected shared assets across non-overlapping appointment windows."""
    now = parse_time(assessed_at, "assessed_at")
    if (
        isinstance(inspection_maximum_age_days, bool)
        or not isinstance(inspection_maximum_age_days, int)
        or not 1 <= inspection_maximum_age_days <= 365
    ):
        raise DomainError("inspection maximum age must be from 1 through 365 days")
    assets: dict[str, tuple[LoanEquipment, datetime, datetime, datetime]] = {}
    for asset in equipment:
        asset_id = clean_code(asset.asset_id, "loan asset id")
        key = asset_id.casefold()
        if key in assets:
            raise DomainError(f"duplicate loan asset id: {asset_id}")
        category = clean_code(asset.category, "loan asset category").casefold()
        available_from = parse_time(asset.available_from, "available_from")
        available_until = parse_time(asset.available_until, "available_until")
        inspected_at = parse_time(asset.inspected_at, "inspected_at")
        if available_until <= available_from:
            raise DomainError(f"asset {asset_id} availability must be ordered")
        if inspected_at > now:
            raise DomainError(f"asset {asset_id} inspection cannot be in the future")
        assets[key] = (
            LoanEquipment(asset_id, category, asset.available_from, asset.available_until, asset.inspected_at),
            available_from,
            available_until,
            inspected_at,
        )
    normalized: list[tuple[EquipmentLoanRequest, datetime, datetime]] = []
    seen: set[str] = set()
    for request in requests:
        request_id = clean_code(request.request_id, "loan request id")
        if request_id.casefold() in seen:
            raise DomainError(f"duplicate loan request id: {request_id}")
        seen.add(request_id.casefold())
        appointment_id = clean_code(request.appointment_id, "loan appointment id")
        category = clean_code(request.category, "loan request category").casefold()
        starts_at = parse_time(request.starts_at, "starts_at")
        ends_at = parse_time(request.ends_at, "ends_at")
        if ends_at <= starts_at:
            raise DomainError(f"request {request_id} window must be ordered")
        if (
            isinstance(request.priority, bool)
            or not isinstance(request.priority, int)
            or not 1 <= request.priority <= 5
        ):
            raise DomainError("loan request priority must be from 1 through 5")
        normalized.append(
            (
                EquipmentLoanRequest(
                    request_id, appointment_id, category, request.starts_at, request.ends_at, request.priority
                ),
                starts_at,
                ends_at,
            )
        )
    normalized.sort(key=lambda row: (-row[0].priority, row[1], row[0].request_id))
    reservations: dict[str, list[tuple[datetime, datetime]]] = {key: [] for key in assets}
    result: list[EquipmentLoanAssignment] = []
    maximum_age = timedelta(days=inspection_maximum_age_days)
    for request, starts_at, ends_at in normalized:
        candidates: list[tuple[datetime, str]] = []
        for key, (asset, available_from, available_until, inspected_at) in assets.items():
            overlaps = any(
                starts_at < booked_end and booked_start < ends_at for booked_start, booked_end in reservations[key]
            )
            if (
                asset.category == request.category
                and available_from <= starts_at
                and available_until >= ends_at
                and starts_at - inspected_at <= maximum_age
                and not overlaps
            ):
                candidates.append((available_until, key))
        if not candidates:
            result.append(EquipmentLoanAssignment(request.request_id, None, False, "no inspected asset is available"))
            continue
        _, selected = min(candidates, key=lambda row: (row[0], assets[row[1]][0].asset_id))
        reservations[selected].append((starts_at, ends_at))
        result.append(
            EquipmentLoanAssignment(
                request.request_id, assets[selected][0].asset_id, True, "earliest-expiring compatible asset"
            )
        )
    return result
