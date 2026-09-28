"""Incremental request metrics accumulators."""

from collections import Counter

from tracelens.analysis.histogram import DurationHistogram
from tracelens.domain.models import LogRecord
from tracelens.domain.results import MetricsSummary


class MetricsAccumulator:
    """Maintain bounded-memory aggregate metrics for log records."""

    def __init__(self) -> None:
        self.request_count = 0
        self.error_count = 0
        self.duration_sum_ms = 0.0
        self.min_duration_ms: float | None = None
        self.max_duration_ms: float | None = None
        self.status_distribution: Counter[int] = Counter()
        self.histogram = DurationHistogram()

    def add(self, record: LogRecord) -> None:
        """Incorporate one validated log record."""
        self.request_count += 1
        self.error_count += int(record.status_code >= 500)
        self.duration_sum_ms += record.duration_ms
        self.min_duration_ms = (
            record.duration_ms
            if self.min_duration_ms is None
            else min(self.min_duration_ms, record.duration_ms)
        )
        self.max_duration_ms = (
            record.duration_ms
            if self.max_duration_ms is None
            else max(self.max_duration_ms, record.duration_ms)
        )
        self.status_distribution[record.status_code] += 1
        self.histogram.add(record.duration_ms)

    def merge(self, other: "MetricsAccumulator") -> None:
        """Combine another accumulator into this one."""
        self.request_count += other.request_count
        self.error_count += other.error_count
        self.duration_sum_ms += other.duration_sum_ms
        if other.min_duration_ms is not None:
            self.min_duration_ms = (
                other.min_duration_ms
                if self.min_duration_ms is None
                else min(self.min_duration_ms, other.min_duration_ms)
            )
        if other.max_duration_ms is not None:
            self.max_duration_ms = (
                other.max_duration_ms
                if self.max_duration_ms is None
                else max(self.max_duration_ms, other.max_duration_ms)
            )
        self.status_distribution.update(other.status_distribution)
        self.histogram.merge(other.histogram)

    def snapshot(self) -> MetricsSummary:
        """Build a serializable snapshot of current aggregate metrics."""
        average = self.duration_sum_ms / self.request_count if self.request_count else None
        error_rate = self.error_count / self.request_count if self.request_count else 0.0
        return MetricsSummary(
            request_count=self.request_count,
            error_count=self.error_count,
            error_rate=error_rate,
            average_duration_ms=average,
            min_duration_ms=self.min_duration_ms,
            max_duration_ms=self.max_duration_ms,
            p50_ms=self.histogram.percentile(50),
            p95_ms=self.histogram.percentile(95),
            p99_ms=self.histogram.percentile(99),
            status_distribution=dict(sorted(self.status_distribution.items())),
        )
