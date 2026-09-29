"""Run a TraceLens benchmark against a supplied or generated JSONL file."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from tracelens.benchmarks import run_benchmark, write_benchmark_result
from tracelens.generation.synthetic import SyntheticLogOptions, generate_logs


def main() -> None:
    """Parse benchmark inputs and write the portable measurement JSON."""
    parser = argparse.ArgumentParser(description="Benchmark TraceLens streaming analysis.")
    parser.add_argument("path", nargs="?", type=Path, help="Existing JSONL input file.")
    parser.add_argument(
        "--records", type=int, help="Generate this many records when no path is supplied."
    )
    parser.add_argument("--output", type=Path, default=Path("benchmark.json"))
    arguments = parser.parse_args()
    if arguments.path is None and arguments.records is None:
        parser.error("provide a JSONL path or --records")
    if arguments.path is not None:
        result = run_benchmark(arguments.path)
    else:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.jsonl"
            generate_logs(path, SyntheticLogOptions(records=arguments.records))
            result = run_benchmark(path)
    write_benchmark_result(result, arguments.output)
    print(f"{result.lines_per_second:.0f} lines/s; peak RSS {result.peak_memory_mb:.1f} MB")


if __name__ == "__main__":
    main()
