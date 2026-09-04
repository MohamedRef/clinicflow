"""Non-clinical equipment calibration readiness checks."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import DomainError, clean_code, parse_time


@dataclass(frozen=True, slots=True)
class EquipmentCalibration:
    asset_id: str
    category: str
    calibrated_at: str
    interval_days: int
    quarantined: bool


@dataclass(frozen=True, slots=True)
class CalibrationUse:
    appointment_id: str
    asset_id: str
    starts_at: str


@dataclass(frozen=True, slots=True)
class CalibrationFinding:
    appointment_id: str
    asset_id: str
    due_at: str
    ready: bool
    reason: str


def assess_equipment_calibration(
    assets: list[EquipmentCalibration], uses: list[CalibrationUse]
) -> list[CalibrationFinding]:
    """Check calibration at the actual appointment instant and fail closed on quarantine."""
    inventory: dict[str, tuple[EquipmentCalibration, datetime]] = {}
    for asset in assets:
        asset_id = clean_code(asset.asset_id, "calibration asset id")
        key = asset_id.casefold()
        if key in inventory:
            raise DomainError(f"duplicate calibration asset: {asset_id}")
        if isinstance(asset.interval_days, bool) or not 1 <= asset.interval_days <= 730:
            raise DomainError("calibration interval must be from 1 through 730 days")
        calibrated = parse_time(asset.calibrated_at, "calibrated_at")
        normalized = EquipmentCalibration(
            asset_id,
            clean_code(asset.category, "asset category"),
            asset.calibrated_at,
            asset.interval_days,
            asset.quarantined,
        )
        inventory[key] = (normalized, calibrated)
    seen: set[tuple[str, str]] = set()
    findings: list[CalibrationFinding] = []
    for use in uses:
        appointment_id = clean_code(use.appointment_id, "calibration appointment id")
        asset_id = clean_code(use.asset_id, "calibration use asset id")
        identity = (appointment_id.casefold(), asset_id.casefold())
        if identity in seen:
            raise DomainError(f"duplicate calibration use: {appointment_id} and {asset_id}")
        seen.add(identity)
        if asset_id.casefold() not in inventory:
            raise DomainError(f"unknown calibration asset: {asset_id}")
        asset, calibrated = inventory[asset_id.casefold()]
        starts_at = parse_time(use.starts_at, "starts_at")
        due_at = calibrated + timedelta(days=asset.interval_days)
        if starts_at < calibrated:
            raise DomainError("equipment use cannot predate calibration")
        ready = not asset.quarantined and starts_at <= due_at
        reason = "calibration current" if ready else "asset quarantined" if asset.quarantined else "calibration expired"
        findings.append(CalibrationFinding(appointment_id, asset.asset_id, due_at.isoformat(), ready, reason))
    return sorted(findings, key=lambda row: (row.ready, row.appointment_id, row.asset_id))
