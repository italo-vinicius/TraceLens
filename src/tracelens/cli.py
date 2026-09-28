"""Command-line entry point for TraceLens."""

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from tracelens.analysis.analyzer import Analyzer
from tracelens.analysis.trace import find_request_trace
from tracelens.domain.models import AnalysisOptions
from tracelens.domain.results import AnalysisResult
from tracelens.parsing.jsonl import StrictParsingError, iter_jsonl
from tracelens.reporting.html_report import write_html_report
from tracelens.reporting.json_report import write_json_report

app = typer.Typer(
    add_completion=False,
    help="Analyze JSONL application logs in a memory-conscious streaming pipeline.",
)
console = Console()


@app.command()
def version() -> None:
    """Show the installed TraceLens version."""
    typer.echo("tracelens 0.1.0")


def _parse_statuses(values: list[str]) -> frozenset[int] | None:
    statuses: set[int] = set()
    for value in values:
        normalized = value.lower()
        if len(normalized) == 3 and normalized[0] in "12345" and normalized[1:] == "xx":
            statuses.update(range(int(normalized[0]) * 100, int(normalized[0]) * 100 + 100))
        elif normalized.isdecimal() and 100 <= int(normalized) <= 599:
            statuses.add(int(normalized))
        else:
            raise typer.BadParameter("use an HTTP code such as 503 or a family such as 5xx")
    return frozenset(statuses) if statuses else None


def _options(
    services: list[str],
    from_at: datetime | None,
    to_at: datetime | None,
    statuses: list[str],
    slow_over_ms: float | None,
) -> AnalysisOptions:
    try:
        return AnalysisOptions(
            services=frozenset(services) or None,
            start_at=from_at,
            end_at=to_at,
            status_codes=_parse_statuses(statuses),
            min_duration_ms=slow_over_ms,
        )
    except ValidationError as error:
        raise typer.BadParameter(str(error)) from error


def _analyze(path: Path, strict: bool, options: AnalysisOptions) -> AnalysisResult:
    if not path.is_file():
        console.print(f"[red]Input file not found:[/] {path}")
        raise typer.Exit(code=2)
    try:
        return Analyzer(options).analyze(iter_jsonl(path, strict=strict), source=str(path))
    except StrictParsingError as error:
        console.print(f"[red]{error}[/]")
        raise typer.Exit(code=2) from error
    except OSError as error:
        console.print(f"[red]Could not read {path}: {error}[/]")
        raise typer.Exit(code=2) from error


def _print_summary(result: AnalysisResult) -> None:
    table = Table(title="TraceLens analysis")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Requests", str(result.overview.request_count))
    table.add_row("Errors", f"{result.overview.error_count} ({result.overview.error_rate:.2%})")
    table.add_row("Average latency", f"{result.overview.average_duration_ms or 0:.1f} ms")
    table.add_row(
        "p50 / p95 / p99",
        f"{result.overview.p50_ms} / {result.overview.p95_ms} / {result.overview.p99_ms} ms",
    )
    table.add_row("Invalid lines", str(result.metadata.invalid_lines))
    table.add_row("Anomalies", str(len(result.anomalies)))
    console.print(table)


@app.command()
def analyze(
    path: Annotated[Path, typer.Argument(help="JSONL input file.")],
    output: Annotated[Path | None, typer.Option(help="Write the full JSON result here.")] = None,
    service: Annotated[
        list[str] | None, typer.Option("--service", help="Include a service; repeatable.")
    ] = None,
    from_at: Annotated[
        datetime | None, typer.Option("--from", help="Inclusive ISO 8601 start.")
    ] = None,
    to_at: Annotated[datetime | None, typer.Option("--to", help="Inclusive ISO 8601 end.")] = None,
    status: Annotated[
        list[str] | None, typer.Option("--status", help="HTTP code or family, e.g. 5xx.")
    ] = None,
    slow_over_ms: Annotated[float | None, typer.Option("--slow-over-ms", min=0)] = None,
    strict: Annotated[bool, typer.Option(help="Stop at the first invalid line.")] = False,
) -> None:
    """Analyze a JSONL file and optionally export the complete JSON contract."""
    result = _analyze(
        path,
        strict,
        _options(service or [], from_at, to_at, status or [], slow_over_ms),
    )
    _print_summary(result)
    if output is not None:
        write_json_report(result, output)
        console.print(f"[green]JSON report written:[/] {output}")


@app.command()
def report(
    path: Annotated[Path, typer.Argument(help="JSONL input file.")],
    output: Annotated[Path, typer.Option(help="Standalone HTML report path.")],
    strict: Annotated[bool, typer.Option(help="Stop at the first invalid line.")] = False,
) -> None:
    """Analyze a JSONL file and write a standalone responsive HTML report."""
    result = _analyze(path, strict, AnalysisOptions())
    write_html_report(result, output)
    _print_summary(result)
    console.print(f"[green]HTML report written:[/] {output}")


@app.command()
def trace(
    path: Annotated[Path, typer.Argument(help="JSONL input file.")],
    request_id: Annotated[str, typer.Option(help="Exact request ID to locate.")],
    strict: Annotated[bool, typer.Option(help="Stop at the first invalid line.")] = False,
) -> None:
    """Find all events for a request ID in a second streaming pass."""
    if not path.is_file():
        console.print(f"[red]Input file not found:[/] {path}")
        raise typer.Exit(code=2)
    try:
        result = find_request_trace(path, request_id, strict=strict)
    except (OSError, StrictParsingError, ValueError) as error:
        console.print(f"[red]{error}[/]")
        raise typer.Exit(code=2) from error
    if result is None:
        console.print(f"[yellow]Request ID not found:[/] {request_id}")
        raise typer.Exit(code=1)
    console.print(f"[bold]REQUEST {result.request_id}[/]")
    for event in result.events:
        console.print(
            f"{event.timestamp:%H:%M:%S.%f}  {event.service:<18} {event.method:<6} "
            f"{event.path:<24} {event.status_code}  {event.duration_ms:g} ms"
        )
    console.print(
        f"Total: {result.total_events} events | Duration: {result.flow_duration_ms / 1_000:.3f} s "
        f"| Final status: {result.final_status_code}"
    )
