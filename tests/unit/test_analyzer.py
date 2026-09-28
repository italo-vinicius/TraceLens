"""Tests for the streaming aggregate analyzer."""

from pathlib import Path

from tracelens.analysis.analyzer import Analyzer
from tracelens.domain.models import AnalysisOptions, LogRecord
from tracelens.parsing.jsonl import InvalidRecord, ValidRecord, iter_jsonl


def valid_record(
    line_number: int,
    *,
    timestamp: str,
    path: str,
    status_code: int = 200,
    duration_ms: float = 10,
    service: str = "orders-api",
) -> ValidRecord:
    return ValidRecord(
        line_number=line_number,
        record=LogRecord.model_validate(
            {
                "timestamp": timestamp,
                "level": "INFO",
                "service": service,
                "method": "GET",
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            }
        ),
    )


def test_analyzer_returns_known_aggregate_metrics() -> None:
    result = Analyzer().analyze(
        iter(
            (
                valid_record(1, timestamp="2026-09-28T14:30:10Z", path="/orders", duration_ms=10),
                InvalidRecord(line_number=2, reason="invalid JSON"),
                valid_record(
                    3,
                    timestamp="2026-09-28T14:30:55Z",
                    path="/orders",
                    status_code=503,
                    duration_ms=100,
                ),
                valid_record(
                    4,
                    timestamp="2026-09-28T14:31:00Z",
                    path="/health",
                    duration_ms=2,
                    service="gateway",
                ),
            )
        ),
        source="fixture.jsonl",
    )

    assert result.metadata.source == "fixture.jsonl"
    assert (
        result.metadata.total_lines,
        result.metadata.valid_lines,
        result.metadata.invalid_lines,
    ) == (4, 3, 1)
    assert result.overview.request_count == 3
    assert result.overview.error_count == 1
    assert result.overview.average_duration_ms == 112 / 3
    assert result.overview.p95_ms == 100
    assert result.status_distribution == {200: 2, 503: 1}
    assert result.service_distribution == {"gateway": 1, "orders-api": 2}
    assert [bucket.request_count for bucket in result.timeline] == [2, 1]
    assert result.invalid_line_summary["invalid JSON"].example_line_numbers == [2]
    assert result.top_requested_endpoints[0].endpoint.path == "/orders"


def test_analyzer_collapses_new_endpoints_after_cardinality_limit() -> None:
    result = Analyzer(AnalysisOptions(max_endpoint_groups=1)).analyze(
        (
            valid_record(1, timestamp="2026-09-28T14:30:10Z", path="/orders"),
            valid_record(2, timestamp="2026-09-28T14:30:20Z", path="/health", duration_ms=50),
            valid_record(3, timestamp="2026-09-28T14:30:30Z", path="/health", duration_ms=50),
        )
    )

    assert result.endpoint_cardinality_truncated
    other = next(item for item in result.top_requested_endpoints if item.endpoint.method == "OTHER")
    assert other.request_count == 2


def test_analyzer_applies_filters_before_aggregation() -> None:
    result = Analyzer(AnalysisOptions(services={"gateway"}, min_duration_ms=10)).analyze(
        (
            valid_record(1, timestamp="2026-09-28T14:30:10Z", path="/orders", duration_ms=10),
            valid_record(
                2,
                timestamp="2026-09-28T14:30:20Z",
                path="/health",
                duration_ms=20,
                service="gateway",
            ),
        )
    )

    assert result.metadata.valid_lines == 2
    assert result.overview.request_count == 1
    assert result.service_distribution == {"gateway": 1}


def test_analyzer_consumes_the_mixed_fixture_as_a_stream() -> None:
    result = Analyzer().analyze(iter_jsonl(Path("tests/fixtures/mixed.jsonl")))

    assert result.metadata.total_lines == 5
    assert result.metadata.valid_lines == 2
    assert result.metadata.invalid_lines == 3
    assert result.overview.request_count == 2
    assert result.status_distribution == {200: 1, 503: 1}


def test_analyzer_attaches_detected_anomalies() -> None:
    records = [
        valid_record(
            line_number,
            timestamp=f"2026-09-28T14:{30 + window:02d}:00Z",
            path="/orders",
            status_code=500 if window == 10 and within_window < 2 else 200,
        )
        for window in range(11)
        for within_window in range(20)
        for line_number in [window * 20 + within_window + 1]
    ]

    result = Analyzer().analyze(records)

    assert [anomaly.type for anomaly in result.anomalies] == ["error_rate_spike"]
