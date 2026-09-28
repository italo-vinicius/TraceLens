# TraceLens

TraceLens analyzes JSONL application logs incrementally, with a focus on predictable memory usage.

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/):

```bash
uv sync --all-extras --dev
uv run tracelens --help
uv run pytest
```

The implementation roadmap and product specification are in
[`TraceLens_IMPLEMENTATION_PLAN.md`](TraceLens_IMPLEMENTATION_PLAN.md).

# TraceLens
