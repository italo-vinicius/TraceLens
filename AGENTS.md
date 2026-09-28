# Repository Guidelines

## Project Structure & Module Organization

TraceLens is a Python 3.12+ package for streaming analysis of JSONL logs. Keep library code in `src/tracelens/`: `domain/` for typed models, `parsing/` for JSONL input, `analysis/` for metrics and anomalies, `reporting/` for JSON/HTML output, and `generation/` for synthetic logs. Keep the Streamlit UI in `dashboard/app.py`; it must consume the library rather than repeat analysis logic. Put tests in `tests/unit/` and `tests/integration/`, shared samples in `tests/fixtures/`, benchmarks in `benchmarks/`, and example logs in `examples/`.

## Build, Test, and Development Commands

Use `uv` for environments and dependencies:

```bash
uv sync --all-extras --dev          # install development and optional dependencies
uv run ruff format .               # apply formatting
uv run ruff check .                # lint
uv run mypy src                    # strict static type checking
uv run pytest --cov=tracelens --cov-fail-under=85  # test with coverage gate
```

Once the CLI is implemented, use `uv run tracelens --help` to discover commands. Typical smoke flows are `tracelens generate --output logs.jsonl --seed 42`, `tracelens analyze logs.jsonl`, and `tracelens report logs.jsonl --output report.html`.

## Coding Style & Naming Conventions

Use four-space indentation, public type hints, and short docstrings where needed. Format and lint with Ruff; keep `mypy` strict for `src/tracelens`. Use `snake_case` for functions, modules, variables, and CLI options; `PascalCase` for classes. Favor small, testable functions and streaming iterators—do not load entire files or introduce Pandas into the analysis core.

## Testing Guidelines

Write pytest tests named `test_<behavior>`. Unit-test parsing, normalization, filters, accumulators, percentiles, cardinality limits, and anomalies. Add integration tests for CLI commands, reports, tracing, and the `generate → analyze → report` flow. Keep fixtures small and generation seeded. Coverage must reach 85%; keep benchmarks separate from CI tests.

## Commit & Pull Request Guidelines

This repository currently has no usable Git history, so no project-specific convention can be inferred. Use concise imperative commit subjects, preferably scoped (for example, `feat(parser): stream JSONL records` or `test: cover strict parsing`). Pull requests should explain the user-visible change, list validation commands run, link relevant issues, and include screenshots for dashboard or HTML-report changes. Do not commit real logs, secrets, or large generated artifacts.

## Configuration & Scope

Treat `TraceLens_IMPLEMENTATION_PLAN.md` as the primary specification. Preserve streaming memory behavior, normalize timestamps to UTC, and keep invalid-line handling explicit (`--strict` versus counted skips). Do not add databases, authentication, real-time ingestion, or external observability integrations to the MVP.
