"""Repeatable benchmark helpers for streaming analysis."""

import platform
import sys
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter, sleep

import orjson
import psutil

from tracelens.analysis.analyzer import Analyzer
from tracelens.parsing.jsonl import iter_jsonl


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Portable measurements from one analysis run."""

    source: str
    total_lines: int
    elapsed_seconds: float
    lines_per_second: float
    peak_memory_mb: float
    python_version: str
    platform: str


def run_benchmark(path: Path) -> BenchmarkResult:
    """Measure one streaming analysis run with approximate sampled peak RSS."""
    process = psutil.Process()
    peak_rss = process.memory_info().rss
    stopped = threading.Event()

    def sample_memory() -> None:
        nonlocal peak_rss
        while not stopped.is_set():
            peak_rss = max(peak_rss, process.memory_info().rss)
            sleep(0.01)

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    started_at = perf_counter()
    try:
        result = Analyzer().analyze(iter_jsonl(path), source=str(path))
    finally:
        stopped.set()
        sampler.join()
    elapsed_seconds = perf_counter() - started_at
    return BenchmarkResult(
        source=str(path),
        total_lines=result.metadata.total_lines,
        elapsed_seconds=elapsed_seconds,
        lines_per_second=result.metadata.total_lines / elapsed_seconds if elapsed_seconds else 0.0,
        peak_memory_mb=peak_rss / (1024 * 1024),
        python_version=sys.version.split()[0],
        platform=platform.platform(),
    )


def write_benchmark_result(result: BenchmarkResult, output: Path) -> None:
    """Write benchmark measurements as readable JSON."""
    output.write_bytes(
        orjson.dumps(asdict(result), option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE)
    )
