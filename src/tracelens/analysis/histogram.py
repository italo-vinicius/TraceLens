"""Bounded-memory histogram for approximate duration percentiles."""

from collections.abc import Sequence
from math import ceil, inf

DURATION_BUCKET_UPPER_BOUNDS: tuple[float, ...] = (
    1,
    2,
    5,
    10,
    20,
    50,
    100,
    200,
    500,
    1_000,
    2_000,
    5_000,
    10_000,
    30_000,
    60_000,
    120_000,
    300_000,
    600_000,
    inf,
)


class DurationHistogram:
    """Incrementally count durations in fixed upper-bound buckets."""

    def __init__(self, upper_bounds: Sequence[float] = DURATION_BUCKET_UPPER_BOUNDS) -> None:
        if not upper_bounds or upper_bounds[-1] != inf:
            raise ValueError("histogram bounds must end with infinity")
        if any(
            left >= right for left, right in zip(upper_bounds[:-1], upper_bounds[1:], strict=True)
        ):
            raise ValueError("histogram bounds must be strictly increasing")
        self._upper_bounds = tuple(upper_bounds)
        self._counts = [0] * len(self._upper_bounds)
        self._count = 0

    @property
    def count(self) -> int:
        """Return the number of values recorded."""
        return self._count

    @property
    def counts(self) -> tuple[int, ...]:
        """Return an immutable view of bucket counts."""
        return tuple(self._counts)

    def add(self, duration_ms: float) -> None:
        """Record a non-negative duration in its first matching bucket."""
        if duration_ms < 0:
            raise ValueError("duration must be non-negative")
        for index, upper_bound in enumerate(self._upper_bounds):
            if duration_ms <= upper_bound:
                self._counts[index] += 1
                self._count += 1
                return
        raise AssertionError("the infinite bucket must accept every finite duration")

    def percentile(self, percentile: float) -> float | None:
        """Return the bucket upper bound at an approximate percentile."""
        if not 0 < percentile <= 100:
            raise ValueError("percentile must be greater than 0 and at most 100")
        if self._count == 0:
            return None
        target = ceil(self._count * percentile / 100)
        running_count = 0
        for upper_bound, count in zip(self._upper_bounds, self._counts, strict=True):
            running_count += count
            if running_count >= target:
                return upper_bound
        raise AssertionError("histogram count and buckets are inconsistent")

    def merge(self, other: "DurationHistogram") -> None:
        """Combine another histogram with the same bucket boundaries."""
        if self._upper_bounds != other._upper_bounds:
            raise ValueError("cannot merge histograms with different bucket bounds")
        self._counts = [
            left + right for left, right in zip(self._counts, other._counts, strict=True)
        ]
        self._count += other._count
