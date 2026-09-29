"""Tests for dashboard adapters that keep uploaded input streaming."""

from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path

from tracelens.analysis.analyzer import Analyzer
from tracelens.dashboard import (
    build_analysis_options,
    build_report_downloads,
    copy_upload_to_tempfile,
)
from tracelens.parsing.jsonl import iter_jsonl


def test_build_analysis_options_normalizes_dashboard_filters() -> None:
    options = build_analysis_options(
        " gateway, orders-api ", ["2xx", "5xx"], date(2026, 9, 28), date(2026, 9, 29), 50
    )

    assert options.services == frozenset({"gateway", "orders-api"})
    assert options.status_codes is not None
    assert 200 in options.status_codes
    assert 503 in options.status_codes
    assert 404 not in options.status_codes
    assert options.start_at == datetime(2026, 9, 28, tzinfo=UTC)
    assert options.end_at == datetime(2026, 9, 29, 23, 59, 59, 999999, tzinfo=UTC)


def test_copy_upload_writes_in_chunks_and_returns_a_temporary_path() -> None:
    path = copy_upload_to_tempfile(BytesIO(b'{"valid": true}\n' * 3))
    try:
        assert path.read_bytes() == b'{"valid": true}\n' * 3
    finally:
        path.unlink()


def test_build_report_downloads_uses_library_report_writers() -> None:
    result = Analyzer().analyze(iter_jsonl(Path("tests/fixtures/mixed.jsonl")))

    json_download, html_download = build_report_downloads(result)

    assert b'"schema_version": "1.0"' in json_download
    assert b"TraceLens report" in html_download
