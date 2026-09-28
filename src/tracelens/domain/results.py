"""Serializable analysis output contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EndpointKey(BaseModel):
    """An HTTP method and normalized path used as an aggregation key."""

    model_config = ConfigDict(frozen=True)

    method: str
    path: str


class MetricsSummary(BaseModel):
    """Aggregate request, error, and latency metrics."""

    request_count: int
    error_count: int
    error_rate: float
    average_duration_ms: float | None
    min_duration_ms: float | None
    max_duration_ms: float | None
    p50_ms: float | None
    p95_ms: float | None
    p99_ms: float | None
    status_distribution: dict[int, int]
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None


class EndpointMetrics(MetricsSummary):
    """Metrics associated with a single endpoint group."""

    endpoint: EndpointKey


class TimelineBucket(MetricsSummary):
    """Metrics collected in one fixed-width UTC time window."""

    started_at: datetime
    finished_at: datetime


class Anomaly(BaseModel):
    """A transparent statistical warning identified in a timeline bucket."""

    started_at: datetime
    finished_at: datetime
    type: Literal["error_rate_spike", "latency_spike"]
    severity: Literal["warning", "critical"]
    observed_value: float
    reference_value: float
    explanation: str


class TraceEvent(BaseModel):
    """A chronological event belonging to one request."""

    timestamp: datetime
    service: str
    method: str
    path: str
    status_code: int
    duration_ms: float


class RequestTrace(BaseModel):
    """Chronological view of all log events for one exact request ID."""

    request_id: str
    events: list[TraceEvent]
    total_events: int
    flow_duration_ms: float
    final_status_code: int


class AnalysisMetadata(BaseModel):
    """Input and processing counts for an analysis run."""

    source: str
    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float
    total_lines: int
    valid_lines: int
    invalid_lines: int
    throughput_lines_per_second: float
    peak_memory_mb: float | None = None


class InvalidLineSummary(BaseModel):
    """Count and bounded source-line examples for a rejection reason."""

    count: int
    example_line_numbers: list[int]


class AnalysisResult(BaseModel):
    """Complete serializable output of the streaming analysis phase."""

    schema_version: Literal["1.0"] = "1.0"
    metadata: AnalysisMetadata
    overview: MetricsSummary
    status_distribution: dict[int, int]
    service_distribution: dict[str, int]
    top_requested_endpoints: list[EndpointMetrics]
    top_error_endpoints: list[EndpointMetrics]
    top_slow_endpoints: list[EndpointMetrics]
    timeline: list[TimelineBucket]
    anomalies: list[Anomaly] = Field(default_factory=list)
    invalid_line_summary: dict[str, InvalidLineSummary]
    endpoint_cardinality_truncated: bool
