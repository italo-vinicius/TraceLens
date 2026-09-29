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

## Synthetic incident and benchmark

Generate reproducible data and a known one-minute incident with:

```bash
uv run tracelens generate --records 100000 --output logs.jsonl --seed 42 --with-incident
uv run tracelens analyze logs.jsonl
uv run tracelens benchmark logs.jsonl --output benchmark.json
```

The incident is injected in the middle of the generated stream. It lasts one minute,
creates `POST /payments` timeouts in `payments-api`, and propagates failures to
`orders-api` and the gateway. With the default 100 ms event interval and 100,000 records,
the window begins at `2026-09-28T15:23:20Z`.

### Initial benchmark results

Measurements run locally on CPython 3.12.14 in WSL2; throughput is informational,
not a CI threshold. Both datasets were generated and read as streams.

| Records | Time | Throughput | Approx. peak RSS |
| ---: | ---: | ---: | ---: |
| 100,000 | 2.10 s | 47,679 lines/s | 29.5 MB |
| 1,000,000 | 21.85 s | 45,767 lines/s | 34.0 MB |

# TraceLens
