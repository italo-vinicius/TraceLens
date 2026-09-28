"""Command-line entry point for TraceLens."""

import typer

app = typer.Typer(
    add_completion=False,
    help="Analyze JSONL application logs in a memory-conscious streaming pipeline.",
)


@app.command()
def version() -> None:
    """Show the installed TraceLens version."""
    typer.echo("tracelens 0.1.0")
