"""End-to-end CLI coverage for analysis, reports, and traces."""

from pathlib import Path

import orjson
from typer.testing import CliRunner

from tracelens.cli import app

runner = CliRunner()


def test_analyze_prints_summary_and_writes_versioned_json(tmp_path: Path) -> None:
    output = tmp_path / "analysis.json"

    result = runner.invoke(app, ["analyze", "tests/fixtures/mixed.jsonl", "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert "TraceLens analysis" in result.output
    payload = orjson.loads(output.read_bytes())
    assert payload["schema_version"] == "1.0"
    assert payload["overview"]["request_count"] == 2
    assert payload["metadata"]["invalid_lines"] == 3


def test_report_writes_standalone_html(tmp_path: Path) -> None:
    output = tmp_path / "report.html"

    result = runner.invoke(app, ["report", "tests/fixtures/mixed.jsonl", "--output", str(output)])

    assert result.exit_code == 0, result.output
    report = output.read_text(encoding="utf-8")
    assert "<style>" in report
    assert "TraceLens report" in report
    assert "HTTP status distribution" in report


def test_trace_displays_events_and_returns_one_when_absent() -> None:
    found = runner.invoke(app, ["trace", "tests/fixtures/trace.jsonl", "--request-id", "req-a912f"])
    missing = runner.invoke(app, ["trace", "tests/fixtures/trace.jsonl", "--request-id", "missing"])

    assert found.exit_code == 0, found.output
    assert "Total: 3 events" in found.output
    assert missing.exit_code == 1
    assert "not found" in missing.output


def test_analyze_rejects_invalid_status_filter() -> None:
    result = runner.invoke(app, ["analyze", "tests/fixtures/mixed.jsonl", "--status", "invalid"])

    assert result.exit_code == 2
    assert "HTTP code" in result.output


def test_generate_and_benchmark_commands(tmp_path: Path) -> None:
    logs = tmp_path / "generated.jsonl"
    benchmark = tmp_path / "benchmark.json"

    generated = runner.invoke(
        app,
        ["generate", "--output", str(logs), "--records", "100", "--seed", "7"],
    )
    measured = runner.invoke(app, ["benchmark", str(logs), "--output", str(benchmark)])

    assert generated.exit_code == 0, generated.output
    assert logs.exists()
    assert measured.exit_code == 0, measured.output
    assert orjson.loads(benchmark.read_bytes())["total_lines"] == 100
