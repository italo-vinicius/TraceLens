"""Small adapters between dashboard inputs and the TraceLens library."""

from datetime import UTC, date, datetime, time
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import BinaryIO

from tracelens.domain.models import AnalysisOptions
from tracelens.domain.results import AnalysisResult
from tracelens.reporting.html_report import write_html_report
from tracelens.reporting.json_report import write_json_report

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
_CHUNK_SIZE = 1024 * 1024


def build_analysis_options(
    services_text: str,
    status_families: list[str],
    start_date: date | None,
    end_date: date | None,
    min_duration_ms: float | None,
) -> AnalysisOptions:
    """Build typed filters from the dashboard controls."""
    services = frozenset(item.strip() for item in services_text.split(",") if item.strip())
    status_codes = frozenset(
        code
        for family in status_families
        for code in range(int(family[0]) * 100, int(family[0]) * 100 + 100)
    )
    start_at = (
        datetime.combine(start_date, time.min, tzinfo=UTC) if start_date is not None else None
    )
    end_at = datetime.combine(end_date, time.max, tzinfo=UTC) if end_date is not None else None
    return AnalysisOptions(
        services=services or None,
        status_codes=status_codes or None,
        start_at=start_at,
        end_at=end_at,
        min_duration_ms=min_duration_ms,
    )


def copy_upload_to_tempfile(upload: BinaryIO) -> Path:
    """Stream an uploaded JSONL file to disk without materializing it in memory."""
    path: Path | None = None
    try:
        with NamedTemporaryFile(delete=False, suffix=".jsonl") as temporary:
            path = Path(temporary.name)
            while chunk := upload.read(_CHUNK_SIZE):
                temporary.write(chunk)
    except BaseException:
        if path is not None:
            path.unlink(missing_ok=True)
        raise
    assert path is not None
    return path


def build_report_downloads(result: AnalysisResult) -> tuple[bytes, bytes]:
    """Render library reports into short-lived files for Streamlit downloads."""
    with TemporaryDirectory() as directory:
        json_path = Path(directory) / "analysis.json"
        html_path = Path(directory) / "report.html"
        write_json_report(result, json_path)
        write_html_report(result, html_path)
        return json_path.read_bytes(), html_path.read_bytes()
