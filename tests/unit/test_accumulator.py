"""Tests for incremental aggregate metrics."""

from tracelens.analysis.accumulator import MetricsAccumulator
from tracelens.domain.models import LogRecord


def record(status_code: int, duration_ms: float) -> LogRecord:
    return LogRecord.model_validate(
        {
            "timestamp": "2026-09-28T14:30:10Z",
            "level": "INFO",
            "service": "orders-api",
            "method": "GET",
            "path": "/orders/{id}",
            "status_code": status_code,
            "duration_ms": duration_ms,
        }
    )


def test_accumulator_tracks_metrics_and_server_errors() -> None:
    accumulator = MetricsAccumulator()
    accumulator.add(record(200, 2))
    accumulator.add(record(404, 10))
    accumulator.add(record(503, 100))

    snapshot = accumulator.snapshot()

    assert snapshot.request_count == 3
    assert snapshot.error_count == 1
    assert snapshot.error_rate == 1 / 3
    assert snapshot.average_duration_ms == 112 / 3
    assert snapshot.min_duration_ms == 2
    assert snapshot.max_duration_ms == 100
    assert snapshot.p50_ms == 10
    assert snapshot.status_distribution == {200: 1, 404: 1, 503: 1}


def test_accumulator_merge_combines_all_metrics() -> None:
    left = MetricsAccumulator()
    right = MetricsAccumulator()
    left.add(record(200, 2))
    right.add(record(500, 200))

    left.merge(right)

    assert left.snapshot().request_count == 2
    assert left.snapshot().error_count == 1
    assert left.snapshot().p99_ms == 200
