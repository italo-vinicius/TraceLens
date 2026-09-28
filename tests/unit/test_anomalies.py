"""Tests for explainable rolling-window anomaly detection."""

from datetime import UTC, datetime, timedelta

from tracelens.analysis.anomalies import AnomalyDetector
from tracelens.domain.results import TimelineBucket


def bucket(
    index: int, *, error_count: int = 0, p95_ms: float = 10, request_count: int = 20
) -> TimelineBucket:
    started_at = datetime(2026, 9, 28, 14, 0, tzinfo=UTC) + timedelta(minutes=index)
    return TimelineBucket(
        started_at=started_at,
        finished_at=started_at + timedelta(minutes=1),
        request_count=request_count,
        error_count=error_count,
        error_rate=error_count / request_count,
        average_duration_ms=p95_ms,
        min_duration_ms=p95_ms,
        max_duration_ms=p95_ms,
        p50_ms=p95_ms,
        p95_ms=p95_ms,
        p99_ms=p95_ms,
        status_distribution={200: request_count - error_count, 500: error_count},
    )


def test_detector_reports_error_rate_spike_after_full_baseline() -> None:
    anomalies = AnomalyDetector().detect(
        [*(bucket(index) for index in range(10)), bucket(10, error_count=2)]
    )

    anomaly = anomalies[0]
    assert anomaly.type == "error_rate_spike"
    assert anomaly.severity == "warning"
    assert anomaly.observed_value == 0.1
    assert "preceding ten windows" in anomaly.explanation


def test_detector_reports_critical_latency_spike() -> None:
    anomalies = AnomalyDetector().detect(
        [*(bucket(index) for index in range(10)), bucket(10, p95_ms=2_000)]
    )

    anomaly = anomalies[0]
    assert anomaly.type == "latency_spike"
    assert anomaly.severity == "critical"
    assert anomaly.reference_value == 10


def test_detector_ignores_normal_or_insufficient_windows() -> None:
    assert AnomalyDetector().detect([bucket(index) for index in range(10)]) == []
    assert (
        AnomalyDetector().detect([*(bucket(index) for index in range(10)), bucket(10, p95_ms=500)])
        == []
    )
    assert (
        AnomalyDetector().detect(
            [*(bucket(index) for index in range(10)), bucket(10, error_count=1, request_count=25)]
        )
        == []
    )
