"""Tests for second-pass request lookup."""

from pathlib import Path

import pytest

from tracelens.analysis.trace import find_request_trace


def test_find_request_trace_sorts_exact_request_events() -> None:
    trace = find_request_trace(Path("tests/fixtures/trace.jsonl"), "req-a912f")

    assert trace is not None
    assert trace.total_events == 3
    assert [event.service for event in trace.events] == ["gateway", "orders-api", "gateway"]
    assert trace.flow_duration_ms == 2_755
    assert trace.final_status_code == 500


def test_find_request_trace_returns_none_when_id_is_missing() -> None:
    assert find_request_trace(Path("tests/fixtures/trace.jsonl"), "absent") is None


def test_find_request_trace_rejects_empty_request_id() -> None:
    with pytest.raises(ValueError, match="request_id"):
        find_request_trace(Path("tests/fixtures/trace.jsonl"), "")
