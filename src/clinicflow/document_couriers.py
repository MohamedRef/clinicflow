"""Schedule sealed administrative-document courier collections."""

from dataclasses import dataclass
from datetime import datetime

from .models import DomainError


@dataclass(frozen=True, slots=True)
class DocumentCourierDemand:
    package_id: str
    site_id: str
    ready_at: datetime
    required_by: datetime
    sealed: bool
    tracked: bool


@dataclass(frozen=True, slots=True)
class DocumentCourierShift:
    shift_id: str
    sites: tuple[str, ...]
    collection_at: datetime
    package_capacity: int


@dataclass(frozen=True, slots=True)
class DocumentCourierAssignment:
    package_id: str
    shift_id: str | None
    assigned: bool
    reason: str


def schedule_document_couriers(
    demands: list[DocumentCourierDemand], shifts: list[DocumentCourierShift]
) -> list[DocumentCourierAssignment]:
    """Reserve the earliest eligible courier while enforcing custody readiness."""
    remaining: list[int] = []
    coverage: list[set[str]] = []
    seen_shifts: set[str] = set()
    for shift in shifts:
        shift_id = _text(shift.shift_id, "document courier shift")
        if (
            shift_id.casefold() in seen_shifts
            or shift.collection_at.tzinfo is None
            or not isinstance(shift.package_capacity, int)
            or isinstance(shift.package_capacity, bool)
            or shift.package_capacity < 1
        ):
            raise DomainError("invalid or duplicate document courier shift")
        seen_shifts.add(shift_id.casefold())
        sites = {_text(site, "courier site").casefold() for site in shift.sites}
        if not sites:
            raise DomainError("document courier shift needs site coverage")
        remaining.append(shift.package_capacity)
        coverage.append(sites)
    seen: set[str] = set()
    normalized: list[tuple[DocumentCourierDemand, str, str]] = []
    for demand in demands:
        package_id = _text(demand.package_id, "document courier package")
        site_id = _text(demand.site_id, "document courier site")
        if (
            package_id.casefold() in seen
            or demand.ready_at.tzinfo is None
            or demand.required_by.tzinfo is None
            or demand.required_by < demand.ready_at
        ):
            raise DomainError("invalid or duplicate document courier demand")
        seen.add(package_id.casefold())
        normalized.append((demand, package_id, site_id.casefold()))
    normalized.sort(key=lambda row: (row[0].required_by, row[1]))
    rows: list[DocumentCourierAssignment] = []
    for demand, package_id, site in normalized:
        if not demand.sealed or not demand.tracked:
            reason = "package_not_sealed" if not demand.sealed else "tracking_not_registered"
            rows.append(DocumentCourierAssignment(package_id, None, False, reason))
            continue
        choices = [
            index
            for index, shift in enumerate(shifts)
            if remaining[index]
            and site in coverage[index]
            and demand.ready_at <= shift.collection_at <= demand.required_by
        ]
        if not choices:
            rows.append(DocumentCourierAssignment(package_id, None, False, "no eligible courier window"))
            continue
        selected = min(choices, key=lambda index: (shifts[index].collection_at, shifts[index].shift_id))
        remaining[selected] -= 1
        rows.append(
            DocumentCourierAssignment(package_id, shifts[selected].shift_id, True, "sealed tracked package scheduled")
        )
    return rows


def _text(value: str, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise DomainError(f"{field} is required")
    return normalized
