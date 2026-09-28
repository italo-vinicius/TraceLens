"""Orchestrate streaming parsing results into aggregate analysis output."""

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from time import perf_counter

from tracelens.analysis.accumulator import MetricsAccumulator
from tracelens.analysis.anomalies import AnomalyDetector
from tracelens.domain.models import AnalysisOptions, LogRecord
from tracelens.domain.results import (
    AnalysisMetadata,
    AnalysisResult,
    EndpointKey,
    EndpointMetrics,
    InvalidLineSummary,
    TimelineBucket,
)
from tracelens.parsing.jsonl import InvalidRecord, ParseResult, ValidRecord

OTHER_ENDPOINT = EndpointKey(method="OTHER", path="OTHER")


class Analyzer:
    """Analyze parsed records incrementally using the supplied options."""

    def __init__(self, options: AnalysisOptions | None = None) -> None:
        self._options = options or AnalysisOptions()

    def analyze(
        self, results: Iterable[ParseResult], *, source: str = "<stream>"
    ) -> AnalysisResult:
        """Consume parse results once and return aggregated metrics."""
        started_at = datetime.now(UTC)
        started_clock = perf_counter()
        total_lines = 0
        valid_lines = 0
        invalid_counts: Counter[str] = Counter()
        invalid_examples: dict[str, list[int]] = {}
        global_metrics = MetricsAccumulator()
        service_distribution: Counter[str] = Counter()
        endpoints: dict[EndpointKey, MetricsAccumulator] = {}
        other_endpoint = MetricsAccumulator()
        timeline: dict[datetime, MetricsAccumulator] = {}
        first_timestamp: datetime | None = None
        last_timestamp: datetime | None = None
        endpoint_cardinality_truncated = False

        for result in results:
            total_lines += 1
            if isinstance(result, InvalidRecord):
                invalid_counts[result.reason] += 1
                invalid_examples.setdefault(result.reason, [])
                if len(invalid_examples[result.reason]) < 5:
                    invalid_examples[result.reason].append(result.line_number)
                continue

            valid_lines += 1
            record = self._record_from(result)
            if not self._options.matches(record):
                continue
            global_metrics.add(record)
            service_distribution[record.service] += 1
            first_timestamp = (
                record.timestamp
                if first_timestamp is None
                else min(first_timestamp, record.timestamp)
            )
            last_timestamp = (
                record.timestamp
                if last_timestamp is None
                else max(last_timestamp, record.timestamp)
            )
            self._add_endpoint(endpoints, other_endpoint, record)
            endpoint_cardinality_truncated |= len(
                endpoints
            ) >= self._options.max_endpoint_groups and (
                EndpointKey(method=record.method, path=record.path) not in endpoints
            )
            bucket_started_at = self._bucket_start(record.timestamp)
            timeline.setdefault(bucket_started_at, MetricsAccumulator()).add(record)

        finished_at = datetime.now(UTC)
        elapsed_seconds = perf_counter() - started_clock
        endpoint_metrics = self._endpoint_metrics(endpoints, other_endpoint)
        invalid_summary = {
            reason: InvalidLineSummary(count=count, example_line_numbers=invalid_examples[reason])
            for reason, count in sorted(invalid_counts.items())
        }
        overview = global_metrics.snapshot().model_copy(
            update={"first_timestamp": first_timestamp, "last_timestamp": last_timestamp}
        )
        timeline_buckets = self._timeline_buckets(timeline)
        return AnalysisResult(
            metadata=AnalysisMetadata(
                source=source,
                started_at=started_at,
                finished_at=finished_at,
                elapsed_seconds=elapsed_seconds,
                total_lines=total_lines,
                valid_lines=valid_lines,
                invalid_lines=total_lines - valid_lines,
                throughput_lines_per_second=total_lines / elapsed_seconds
                if elapsed_seconds
                else 0.0,
            ),
            overview=overview,
            status_distribution=overview.status_distribution,
            service_distribution=dict(sorted(service_distribution.items())),
            top_requested_endpoints=self._rank(endpoint_metrics, key="request_count"),
            top_error_endpoints=self._rank(endpoint_metrics, key="error_count"),
            top_slow_endpoints=self._rank(endpoint_metrics, key="average_duration_ms"),
            timeline=timeline_buckets,
            anomalies=AnomalyDetector().detect(timeline_buckets),
            invalid_line_summary=invalid_summary,
            endpoint_cardinality_truncated=endpoint_cardinality_truncated,
        )

    @staticmethod
    def _record_from(result: ValidRecord) -> LogRecord:
        return result.record

    def _add_endpoint(
        self,
        endpoints: dict[EndpointKey, MetricsAccumulator],
        other_endpoint: MetricsAccumulator,
        record: LogRecord,
    ) -> None:
        endpoint = EndpointKey(method=record.method, path=record.path)
        accumulator = endpoints.get(endpoint)
        if accumulator is not None:
            accumulator.add(record)
            return
        if len(endpoints) < self._options.max_endpoint_groups:
            endpoints[endpoint] = MetricsAccumulator()
            endpoints[endpoint].add(record)
            return
        other_endpoint.add(record)

    def _bucket_start(self, timestamp: datetime) -> datetime:
        seconds = int(timestamp.timestamp())
        bucket_seconds = self._options.time_bucket_seconds
        return datetime.fromtimestamp(seconds - seconds % bucket_seconds, tz=UTC)

    def _endpoint_metrics(
        self,
        endpoints: dict[EndpointKey, MetricsAccumulator],
        other_endpoint: MetricsAccumulator,
    ) -> list[EndpointMetrics]:
        metrics = [
            EndpointMetrics(endpoint=endpoint, **accumulator.snapshot().model_dump())
            for endpoint, accumulator in endpoints.items()
        ]
        if other_endpoint.request_count:
            metrics.append(
                EndpointMetrics(endpoint=OTHER_ENDPOINT, **other_endpoint.snapshot().model_dump())
            )
        return metrics

    def _rank(self, metrics: list[EndpointMetrics], *, key: str) -> list[EndpointMetrics]:
        def sort_key(metric: EndpointMetrics) -> tuple[float, str, str]:
            value = getattr(metric, key)
            return (-float(value or 0), metric.endpoint.method, metric.endpoint.path)

        return sorted(metrics, key=sort_key)[: self._options.ranking_limit]

    def _timeline_buckets(
        self, timeline: dict[datetime, MetricsAccumulator]
    ) -> list[TimelineBucket]:
        bucket_duration = timedelta(seconds=self._options.time_bucket_seconds)
        return [
            TimelineBucket(
                started_at=started_at,
                finished_at=started_at + bucket_duration,
                **accumulator.snapshot().model_dump(),
            )
            for started_at, accumulator in sorted(timeline.items())
        ]
