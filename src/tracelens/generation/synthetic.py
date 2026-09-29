"""Generate reproducible JSONL application logs with an optional incident."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from random import Random

import orjson

BASE_TIMESTAMP = datetime(2026, 9, 28, 14, 0, tzinfo=UTC)
RECORD_INTERVAL = timedelta(milliseconds=100)
INCIDENT_DURATION = timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class SyntheticLogOptions:
    """Parameters controlling deterministic synthetic JSONL generation."""

    records: int = 100_000
    seed: int = 42
    error_rate: float = 0.01
    invalid_line_rate: float = 0.0
    with_incident: bool = False

    def __post_init__(self) -> None:
        if self.records <= 0:
            raise ValueError("records must be greater than zero")
        if not 0 <= self.error_rate <= 1:
            raise ValueError("error_rate must be between zero and one")
        if not 0 <= self.invalid_line_rate <= 1:
            raise ValueError("invalid_line_rate must be between zero and one")


@dataclass(frozen=True, slots=True)
class GenerationSummary:
    """Facts about a generated dataset and its known incident window."""

    output: Path
    records_requested: int
    invalid_lines: int
    incident_started_at: datetime | None
    incident_finished_at: datetime | None


def _endpoint(random: Random, service: str) -> tuple[str, str]:
    endpoints = {
        "gateway": (("GET", "/orders/{id}"), ("GET", "/health"), ("GET", "/products")),
        "orders-api": (("GET", "/orders/{id}"), ("POST", "/orders"), ("GET", "/orders")),
        "payments-api": (("POST", "/payments"), ("GET", "/payments/{id}")),
        "notifications-worker": (("POST", "/notifications"), ("GET", "/health")),
    }
    return random.choice(endpoints[service])


def _normal_status(random: Random, error_rate: float) -> tuple[int, str | None]:
    if random.random() < error_rate:
        return random.choice(
            ((500, "InternalServerError"), (502, "UpstreamFailure"), (504, "Timeout"))
        )
    if random.random() < 0.05:
        return random.choice(((400, None), (404, None), (409, None)))
    return random.choice(((200, None), (200, None), (201, None), (204, None)))


def _normal_duration(random: Random) -> float:
    duration = random.expovariate(1 / 45)
    if random.random() < 0.02:
        duration += random.uniform(250, 1_500)
    return round(duration, 3)


def _incident_record(random: Random, offset: int) -> tuple[str, str, str, int, float, str]:
    if offset % 3 == 0:
        return (
            "payments-api",
            "POST",
            "/payments",
            504,
            round(random.uniform(1_500, 2_500), 3),
            "Timeout",
        )
    if offset % 3 == 1:
        return (
            "orders-api",
            "POST",
            "/orders",
            502,
            round(random.uniform(800, 1_800), 3),
            "UpstreamFailure",
        )
    return (
        "gateway",
        "GET",
        "/orders/{id}",
        500,
        round(random.uniform(500, 1_500), 3),
        "UpstreamFailure",
    )


def generate_logs(output: Path, options: SyntheticLogOptions) -> GenerationSummary:
    """Write a JSONL dataset one record at a time and return its generation facts."""
    random = Random(options.seed)
    incident_records = int(INCIDENT_DURATION / RECORD_INTERVAL)
    incident_start_index = options.records // 2
    incident_end_index = min(incident_start_index + incident_records, options.records)
    invalid_lines = 0
    with output.open("wb") as stream:
        for index in range(options.records):
            if random.random() < options.invalid_line_rate:
                stream.write(b"{invalid synthetic line}\n")
                invalid_lines += 1
                continue
            timestamp = BASE_TIMESTAMP + index * RECORD_INTERVAL
            request_id = f"req-{index // 3:08d}"
            is_incident = (
                options.with_incident and incident_start_index <= index < incident_end_index
            )
            error_type: str | None
            if is_incident:
                service, method, path, status_code, duration_ms, error_type = _incident_record(
                    random, index - incident_start_index
                )
            else:
                service = random.choices(
                    ("gateway", "orders-api", "payments-api", "notifications-worker"),
                    weights=(45, 30, 18, 7),
                )[0]
                method, path = _endpoint(random, service)
                status_code, error_type = _normal_status(random, options.error_rate)
                duration_ms = _normal_duration(random)
            payload: dict[str, object] = {
                "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                "level": "ERROR" if status_code >= 500 else "INFO",
                "service": service,
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "request_id": request_id,
                "message": "Synthetic application log event",
                "metadata": {"region": "sa-east-1", "synthetic": True},
            }
            if error_type is not None:
                payload["error_type"] = error_type
            stream.write(orjson.dumps(payload))
            stream.write(b"\n")
    incident_started_at = (
        BASE_TIMESTAMP + incident_start_index * RECORD_INTERVAL if options.with_incident else None
    )
    return GenerationSummary(
        output=output,
        records_requested=options.records,
        invalid_lines=invalid_lines,
        incident_started_at=incident_started_at,
        incident_finished_at=incident_started_at + INCIDENT_DURATION
        if incident_started_at
        else None,
    )
