"""Interactive Streamlit dashboard for the TraceLens streaming library."""

from datetime import date
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from tracelens.analysis.analyzer import Analyzer
from tracelens.analysis.trace import find_request_trace
from tracelens.dashboard import (
    MAX_UPLOAD_BYTES,
    build_analysis_options,
    build_report_downloads,
    copy_upload_to_tempfile,
)
from tracelens.domain.results import AnalysisResult, RequestTrace
from tracelens.parsing.jsonl import StrictParsingError, iter_jsonl

_ROOT = Path(__file__).resolve().parents[1]
_SAMPLE_PATH = _ROOT / "examples" / "sample.jsonl"


def _endpoint_rows(result: AnalysisResult) -> list[dict[str, Any]]:
    return [
        {
            "Endpoint": f"{item.endpoint.method} {item.endpoint.path}",
            "Requests": item.request_count,
            "Errors": item.error_count,
            "Error rate": f"{item.error_rate:.2%}",
            "p95 (ms)": item.p95_ms,
        }
        for item in result.top_requested_endpoints
    ]


def _show_result(result: AnalysisResult) -> None:
    overview = result.overview
    metrics = st.columns(5)
    metrics[0].metric("Requests", f"{overview.request_count:,}")
    metrics[1].metric("Errors", f"{overview.error_rate:.2%}", f"{overview.error_count:,} events")
    metrics[2].metric("Average latency", f"{overview.average_duration_ms or 0:.1f} ms")
    metrics[3].metric("p95 latency", f"{overview.p95_ms or 0:.0f} ms")
    metrics[4].metric("Anomalies", len(result.anomalies))

    if result.metadata.invalid_lines:
        st.warning(f"Skipped {result.metadata.invalid_lines:,} invalid line(s).")
    if result.endpoint_cardinality_truncated:
        st.warning("Endpoint grouping reached its safety limit; additional groups are in OTHER.")

    st.subheader("Timeline")
    timeline = result.timeline
    chart = go.Figure()
    chart.add_scatter(
        x=[bucket.started_at for bucket in timeline],
        y=[bucket.request_count for bucket in timeline],
        mode="lines",
        name="Requests",
    )
    chart.add_scatter(
        x=[bucket.started_at for bucket in timeline],
        y=[bucket.error_rate * 100 for bucket in timeline],
        mode="lines",
        name="Error rate (%)",
        yaxis="y2",
    )
    chart.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        yaxis2=dict(overlaying="y", side="right", title="Error rate (%)"),
        legend=dict(orientation="h"),
    )
    st.plotly_chart(chart, width="stretch")

    left, right = st.columns(2)
    with left:
        st.subheader("Most requested endpoints")
        st.dataframe(_endpoint_rows(result), width="stretch", hide_index=True)
    with right:
        st.subheader("Anomalies")
        if result.anomalies:
            st.dataframe(
                [
                    {
                        "Window": anomaly.started_at.isoformat(),
                        "Type": anomaly.type.replace("_", " "),
                        "Severity": anomaly.severity,
                        "Observed": round(anomaly.observed_value, 3),
                        "Reference": round(anomaly.reference_value, 3),
                    }
                    for anomaly in result.anomalies
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("No anomalies were detected for these filters.")


def _show_trace(trace: RequestTrace | None, request_id: str) -> None:
    if not request_id:
        return
    st.subheader("Request trace")
    if trace is None:
        st.info(f"No events found for request ID {request_id!r}.")
        return
    st.caption(
        f"{trace.total_events} events · {trace.flow_duration_ms / 1_000:.3f} s · "
        f"final status {trace.final_status_code}"
    )
    st.dataframe(
        [event.model_dump(mode="json") for event in trace.events],
        width="stretch",
        hide_index=True,
    )


def main() -> None:
    """Render the dashboard and perform analysis only after user action."""
    st.set_page_config(page_title="TraceLens", page_icon="🔎", layout="wide")
    st.title("TraceLens")
    st.caption("Streaming JSONL log analysis. Uploaded files are processed from a temporary file.")

    source_kind = st.radio("Source", ["Built-in example", "Upload JSONL"], horizontal=True)
    upload = None
    if source_kind == "Upload JSONL":
        upload = st.file_uploader("JSONL log file", type=["jsonl"])
        st.caption("Public demo limit: 100 MB. For larger files, use the TraceLens CLI.")

    with st.expander("Filters", expanded=True):
        filter_columns = st.columns(3)
        services = filter_columns[0].text_input("Services (comma-separated)")
        status_families = filter_columns[1].multiselect(
            "HTTP status families", ["1xx", "2xx", "3xx", "4xx", "5xx"]
        )
        use_min_duration = filter_columns[2].checkbox("Filter minimum duration")
        min_duration = filter_columns[2].number_input(
            "Minimum duration (ms)", min_value=0.0, value=0.0, disabled=not use_min_duration
        )
        start_date = filter_columns[0].date_input("From (UTC)", value=None)
        end_date = filter_columns[1].date_input("To (UTC)", value=None)
        strict = filter_columns[2].checkbox(
            "Strict parsing", help="Stop at the first invalid line."
        )
        request_id = st.text_input("Request ID to trace (optional)")

    if st.button("Analyze logs", type="primary"):
        if source_kind == "Upload JSONL" and upload is None:
            st.error("Select a .jsonl file before analyzing.")
            return
        if upload is not None and upload.size > MAX_UPLOAD_BYTES:
            st.error("This demo accepts files up to 100 MB. Use the CLI for larger files.")
            return

        temporary_path: Path | None = None
        try:
            options = build_analysis_options(
                services,
                status_families,
                start_date if isinstance(start_date, date) else None,
                end_date if isinstance(end_date, date) else None,
                min_duration if use_min_duration else None,
            )
            if upload is None:
                source_path = _SAMPLE_PATH
                source_label = "examples/sample.jsonl"
            else:
                temporary_path = copy_upload_to_tempfile(upload)
                source_path = temporary_path
                source_label = upload.name
            with st.spinner("Analyzing log stream..."):
                result = Analyzer(options).analyze(
                    iter_jsonl(source_path, strict=strict), source=source_label
                )
                trace = (
                    find_request_trace(source_path, request_id, strict=strict)
                    if request_id
                    else None
                )
                json_download, html_download = build_report_downloads(result)
            st.session_state["analysis"] = result
            st.session_state["trace"] = trace
            st.session_state["trace_request_id"] = request_id
            st.session_state["json_download"] = json_download
            st.session_state["html_download"] = html_download
        except (OSError, StrictParsingError, ValueError) as error:
            st.error(f"Could not analyze this file: {error}")
            return
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    result = st.session_state.get("analysis")
    if isinstance(result, AnalysisResult):
        _show_result(result)
        _show_trace(st.session_state.get("trace"), st.session_state.get("trace_request_id", ""))
        downloads = st.columns(2)
        downloads[0].download_button(
            "Download JSON result",
            data=st.session_state["json_download"],
            file_name="tracelens-analysis.json",
            mime="application/json",
        )
        downloads[1].download_button(
            "Download HTML report",
            data=st.session_state["html_download"],
            file_name="tracelens-report.html",
            mime="text/html",
        )


if __name__ == "__main__":
    main()
