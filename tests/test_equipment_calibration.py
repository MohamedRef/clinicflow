import pytest

from clinicflow import CalibrationUse, DomainError, EquipmentCalibration, assess_equipment_calibration


def test_equipment_calibration_is_checked_at_use_time() -> None:
    asset = EquipmentCalibration("device", "monitor", "2026-08-01T08:00:00+02:00", 30, False)
    rows = assess_equipment_calibration(
        [asset],
        [
            CalibrationUse("late", "device", "2026-09-01T08:00:01+02:00"),
            CalibrationUse("current", "DEVICE", "2026-08-31T08:00:00+02:00"),
        ],
    )
    assert [row.appointment_id for row in rows] == ["late", "current"]
    assert rows[0].reason == "calibration expired"
    assert rows[1].ready is True


def test_equipment_calibration_rejects_case_aliased_assets() -> None:
    rows = [
        EquipmentCalibration("Device", "monitor", "2026-08-01T08:00:00Z", 30, False),
        EquipmentCalibration("device", "monitor", "2026-08-01T08:00:00Z", 30, False),
    ]
    with pytest.raises(DomainError, match="duplicate"):
        assess_equipment_calibration(rows, [])
