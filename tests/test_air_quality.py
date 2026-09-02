import pytest

from clinicflow import DomainError, RoomAirPolicy, RoomAirReading, assess_room_air_quality


def test_air_quality_uses_latest_reading_and_reports_exceeded_metrics() -> None:
    readings = [
        RoomAirReading("room-a", 10, 1_500, 5),
        RoomAirReading("room-a", 20, 700, 40),
    ]
    [finding] = assess_room_air_quality(readings, [RoomAirPolicy("room-a", 15, 1_000, 25)], 30)
    assert finding.age_minutes == 10
    assert finding.exceeded_metrics == ("particulate",)
    assert not finding.ready


def test_air_quality_reports_rooms_without_readings() -> None:
    [finding] = assess_room_air_quality([], [RoomAirPolicy("room-a", 15, 1_000, 25)], 30)
    assert finding.stale
    assert finding.exceeded_metrics == ("missing",)


def test_air_quality_rejects_future_readings() -> None:
    with pytest.raises(DomainError, match="future"):
        assess_room_air_quality([RoomAirReading("room-a", 31, 500, 5)], [RoomAirPolicy("room-a", 15, 1_000, 25)], 30)
