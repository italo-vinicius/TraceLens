"""Tests for deterministic synthetic log generation."""

from pathlib import Path

from tracelens.analysis.analyzer import Analyzer
from tracelens.analysis.trace import find_request_trace
from tracelens.generation.synthetic import SyntheticLogOptions, generate_logs
from tracelens.parsing.jsonl import iter_jsonl


def test_same_seed_generates_identical_content(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    options = SyntheticLogOptions(records=500, seed=123, invalid_line_rate=0.02)

    generate_logs(first, options)
    generate_logs(second, options)

    assert first.read_bytes() == second.read_bytes()


def test_incident_is_detected_and_has_correlated_request_events(tmp_path: Path) -> None:
    output = tmp_path / "incident.jsonl"
    summary = generate_logs(
        output, SyntheticLogOptions(records=12_600, seed=42, with_incident=True)
    )

    result = Analyzer().analyze(iter_jsonl(output))
    trace = find_request_trace(output, "req-00002100")

    assert summary.incident_started_at is not None
    assert {anomaly.type for anomaly in result.anomalies} == {"error_rate_spike", "latency_spike"}
    assert trace is not None
    assert trace.total_events == 3
    assert {event.service for event in trace.events} == {"gateway", "orders-api", "payments-api"}


def test_generator_can_emit_invalid_lines(tmp_path: Path) -> None:
    output = tmp_path / "invalid.jsonl"

    summary = generate_logs(output, SyntheticLogOptions(records=10, invalid_line_rate=1))
    result = Analyzer().analyze(iter_jsonl(output))

    assert summary.invalid_lines == 10
    assert result.metadata.invalid_lines == 10
