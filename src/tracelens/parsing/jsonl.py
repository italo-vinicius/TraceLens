"""Streaming parser for newline-delimited JSON log files."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import orjson
from pydantic import ValidationError

from tracelens.domain.models import LogRecord


class StrictParsingError(ValueError):
    """Raised when strict parsing encounters an invalid input line."""

    def __init__(self, line_number: int, reason: str) -> None:
        super().__init__(f"Invalid JSONL record on line {line_number}: {reason}")
        self.line_number = line_number
        self.reason = reason


@dataclass(frozen=True, slots=True)
class ValidRecord:
    """A successfully parsed record and its source line number."""

    line_number: int
    record: LogRecord


@dataclass(frozen=True, slots=True)
class InvalidRecord:
    """A rejected record with a concise, user-safe reason."""

    line_number: int
    reason: str


ParseResult = ValidRecord | InvalidRecord


def _validation_reason(error: ValidationError) -> str:
    first_error = error.errors(include_url=False)[0]
    location = ".".join(str(part) for part in first_error["loc"])
    return f"{location}: {first_error['msg']}"


def _parse_line(line: bytes, line_number: int) -> ParseResult:
    if not line.strip():
        return InvalidRecord(line_number=line_number, reason="empty line")
    try:
        payload = orjson.loads(line)
    except orjson.JSONDecodeError:
        return InvalidRecord(line_number=line_number, reason="invalid JSON")
    if not isinstance(payload, dict):
        return InvalidRecord(line_number=line_number, reason="JSON value must be an object")
    try:
        return ValidRecord(line_number=line_number, record=LogRecord.model_validate(payload))
    except ValidationError as error:
        return InvalidRecord(line_number=line_number, reason=_validation_reason(error))


def iter_jsonl(path: Path, *, strict: bool = False) -> Iterator[ParseResult]:
    """Yield parse results one input line at a time without retaining the file."""
    with path.open("rb") as stream:
        for line_number, line in enumerate(stream, start=1):
            result = _parse_line(line, line_number)
            if strict and isinstance(result, InvalidRecord):
                raise StrictParsingError(result.line_number, result.reason)
            yield result
