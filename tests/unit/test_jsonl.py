"""Tests for the JSONL streaming parser."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from tracelens.parsing.jsonl import InvalidRecord, StrictParsingError, ValidRecord, iter_jsonl


def test_iter_jsonl_yields_mixed_results_without_a_list() -> None:
    results: Iterator[ValidRecord | InvalidRecord] = iter_jsonl(Path("tests/fixtures/mixed.jsonl"))

    assert not isinstance(results, list)
    first = next(results)
    remainder = list(results)

    assert isinstance(first, ValidRecord)
    assert first.line_number == 1
    assert first.record.method == "GET"
    assert [result.line_number for result in remainder] == [2, 3, 4, 5]
    assert sum(isinstance(result, InvalidRecord) for result in remainder) == 3
    assert isinstance(remainder[-1], ValidRecord)


def test_iter_jsonl_strict_stops_at_first_invalid_record() -> None:
    results = iter_jsonl(Path("tests/fixtures/mixed.jsonl"), strict=True)

    assert isinstance(next(results), ValidRecord)
    with pytest.raises(StrictParsingError, match="line 2") as error:
        next(results)

    assert error.value.line_number == 2
    assert error.value.reason == "invalid JSON"
