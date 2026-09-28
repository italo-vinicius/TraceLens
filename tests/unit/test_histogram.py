"""Tests for bounded-memory duration percentiles."""

from math import inf

import pytest

from tracelens.analysis.histogram import DurationHistogram


def test_histogram_returns_bucket_upper_bounds_for_percentiles() -> None:
    histogram = DurationHistogram()
    for duration in (0.5, 1, 4.9, 5, 2_500, 700_000):
        histogram.add(duration)

    assert histogram.count == 6
    assert histogram.percentile(50) == 5
    assert histogram.percentile(95) == inf


def test_histogram_merge_combines_counts() -> None:
    left = DurationHistogram()
    right = DurationHistogram()
    left.add(2)
    right.add(10)

    left.merge(right)

    assert left.count == 2
    assert left.percentile(50) == 2
    assert left.percentile(100) == 10


@pytest.mark.parametrize("percentile", (0, 100.1))
def test_histogram_rejects_invalid_percentile(percentile: float) -> None:
    with pytest.raises(ValueError, match="percentile"):
        DurationHistogram().percentile(percentile)
