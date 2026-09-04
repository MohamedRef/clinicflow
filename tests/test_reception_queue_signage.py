from clinicflow import QueueSign, ReceptionLane, assess_reception_queue_signage


def test_reports_missing_and_stale_queue_signs() -> None:
    rows = assess_reception_queue_signage(
        [ReceptionLane("missing", "check-in", True), ReceptionLane("stale", "payments", True)],
        [QueueSign("stale", "check-in", True)],
    )
    assert [row.state for row in rows] == ["missing", "stale"]
