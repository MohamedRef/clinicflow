import pytest

from clinicflow import NoiseReading, assess_waiting_room_noise
from clinicflow.models import DomainError


def test_prioritizes_relocation_mitigation_and_remeasurement() -> None:
    rows = assess_waiting_room_noise(
        [
            NoiseReading("lobby", 65, False, True, 5),
            NoiseReading("quiet", 58, True, False, 2),
            NoiseReading("family", 70, False, True, 4),
            NoiseReading("overflow", 40, False, True, 45),
        ]
    )
    assert [row.state for row in rows] == ["relocate", "mitigate", "remeasure", "acceptable"]
    assert rows[0].reasons == ("limit_exceeded", "mitigation_unavailable")
    assert rows[1].priority == 205


def test_validates_noise_policy_and_readings() -> None:
    with pytest.raises(DomainError, match="ordered"):
        assess_waiting_room_noise([], quiet_limit=70, standard_limit=60)
    with pytest.raises(DomainError, match="positive"):
        assess_waiting_room_noise([], stale_after_minutes=0)
    with pytest.raises(DomainError, match="between"):
        assess_waiting_room_noise([NoiseReading("lobby", 141, False, True, 0)])
    with pytest.raises(DomainError, match="negative"):
        assess_waiting_room_noise([NoiseReading("lobby", 40, False, True, -1)])
    with pytest.raises(DomainError, match="duplicate"):
        assess_waiting_room_noise(
            [NoiseReading("Lobby", 40, False, True, 0), NoiseReading(" lobby ", 41, False, True, 0)]
        )
