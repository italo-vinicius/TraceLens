"""Standalone responsive HTML reporting."""

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from tracelens.domain.results import AnalysisResult, TimelineBucket

_ENVIRONMENT = Environment(
    loader=PackageLoader("tracelens.reporting", "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


def _line_points(values: list[float], width: int = 880, height: int = 180) -> str:
    if not values:
        return ""
    maximum = max(values) or 1
    step = width / max(len(values) - 1, 1)
    return " ".join(
        f"{index * step:.1f},{height - value / maximum * height:.1f}"
        for index, value in enumerate(values)
    )


def _timeline_chart(timeline: list[TimelineBucket]) -> dict[str, str]:
    return {
        "requests": _line_points([float(bucket.request_count) for bucket in timeline]),
        "errors": _line_points([float(bucket.error_count) for bucket in timeline]),
        "p95": _line_points([bucket.p95_ms or 0 for bucket in timeline]),
    }


def write_html_report(result: AnalysisResult, output: Path) -> None:
    """Write a self-contained HTML report that opens without a server."""
    template = _ENVIRONMENT.get_template("report.html.j2")
    output.write_text(
        template.render(result=result, chart=_timeline_chart(result.timeline)), encoding="utf-8"
    )
