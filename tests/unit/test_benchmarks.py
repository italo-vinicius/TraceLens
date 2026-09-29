"""Tests for portable streaming benchmark output."""

from pathlib import Path

import orjson

from tracelens.benchmarks import run_benchmark, write_benchmark_result
from tracelens.generation.synthetic import SyntheticLogOptions, generate_logs


def test_benchmark_measures_generated_file_and_writes_json(tmp_path: Path) -> None:
    source = tmp_path / "input.jsonl"
    output = tmp_path / "benchmark.json"
    generate_logs(source, SyntheticLogOptions(records=100))

    result = run_benchmark(source)
    write_benchmark_result(result, output)

    assert result.total_lines == 100
    assert result.elapsed_seconds > 0
    assert result.lines_per_second > 0
    assert result.peak_memory_mb > 0
    assert orjson.loads(output.read_bytes())["total_lines"] == 100
