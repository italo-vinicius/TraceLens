"""Tests for validated log contracts and filters."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tracelens.domain.models import AnalysisOptions, LogRecord


def make_record(**changes: object) -> LogRecord:
    values: dict[str, object] = {
        "timestamp": "2026-09-28T14:30:10-03:00",
        "level": "info",
        "service": " orders-api ",
        "method": "get",
        "path": "/orders/{id}",
        "status_code": 200,
        "duration_ms": 12.5,
    }
    values.update(changes)
    return LogRecord.model_validate(values)


def test_log_record_normalizes_values() -> None:
    record = make_record()

    assert record.level == "INFO"
    assert record.service == "orders-api"
    assert record.method == "GET"
    assert record.timestamp == datetime(2026, 9, 28, 17, 30, 10, tzinfo=UTC)


@pytest.mark.parametrize(
    ("field", "value"),
    [("path", "orders"), ("status_code", 99), ("duration_ms", -0.1), ("level", "verbose")],
)
def test_log_record_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        make_record(**{field: value})


def test_log_record_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="UTC offset"):
        make_record(timestamp="2026-09-28T14:30:10")


def test_analysis_options_combines_filters() -> None:
    options = AnalysisOptions(
        start_at="2026-09-28T17:00:00Z",
        end_at="2026-09-28T18:00:00Z",
        services={"orders-api"},
        status_codes={200},
        min_duration_ms=10,
    )

    assert options.matches(make_record())
    assert not options.matches(make_record(duration_ms=9.9))
    assert not options.matches(make_record(service="billing-api"))
