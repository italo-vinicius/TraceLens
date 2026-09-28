"""Validated log records and analysis filters."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LogRecord(BaseModel):
    """One normalized application log event."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    timestamp: datetime
    level: str
    service: Annotated[str, Field(min_length=1)]
    method: Annotated[str, Field(min_length=1)]
    path: Annotated[str, Field(min_length=1)]
    status_code: Annotated[int, Field(ge=100, le=599)]
    duration_ms: Annotated[float, Field(ge=0)]
    request_id: str | None = None
    message: str | None = None
    error_type: str | None = None
    metadata: dict[str, object] | None = None

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        """Require an offset-aware timestamp and convert it to UTC."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a UTC offset")
        return value.astimezone(UTC)

    @field_validator("level")
    @classmethod
    def normalize_level(cls, value: str) -> str:
        """Normalize and validate the application log level."""
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        return normalized

    @field_validator("service")
    @classmethod
    def validate_service(cls, value: str) -> str:
        """Reject whitespace-only service names."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("service must not be empty")
        return normalized

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        """Normalize HTTP methods to uppercase."""
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("method must not be empty")
        return normalized

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        """Require an absolute request path."""
        if not value.startswith("/"):
            raise ValueError("path must start with '/'")
        return value


class AnalysisOptions(BaseModel):
    """Optional predicates applied before log aggregation."""

    model_config = ConfigDict(frozen=True)

    start_at: datetime | None = None
    end_at: datetime | None = None
    services: frozenset[str] | None = None
    status_codes: frozenset[int] | None = None
    min_duration_ms: Annotated[float | None, Field(ge=0)] = None
    time_bucket_seconds: Annotated[int, Field(gt=0)] = 60
    max_endpoint_groups: Annotated[int, Field(gt=0)] = 10_000
    ranking_limit: Annotated[int, Field(gt=0)] = 20

    @field_validator("start_at", "end_at")
    @classmethod
    def normalize_boundary(cls, value: datetime | None) -> datetime | None:
        """Normalize supplied time bounds to UTC."""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("time bounds must include a UTC offset")
        return value.astimezone(UTC)

    @field_validator("services")
    @classmethod
    def normalize_services(cls, value: frozenset[str] | None) -> frozenset[str] | None:
        """Discard accidental surrounding whitespace in service filters."""
        if value is None:
            return None
        return frozenset(service.strip() for service in value if service.strip())

    def matches(self, record: LogRecord) -> bool:
        """Return whether a record satisfies every configured filter."""
        if self.start_at is not None and record.timestamp < self.start_at:
            return False
        if self.end_at is not None and record.timestamp > self.end_at:
            return False
        if self.services is not None and record.service not in self.services:
            return False
        if self.status_codes is not None and record.status_code not in self.status_codes:
            return False
        return self.min_duration_ms is None or record.duration_ms >= self.min_duration_ms
