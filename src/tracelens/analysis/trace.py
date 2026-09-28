"""Second-pass request trace lookup without retaining IDs during analysis."""

from pathlib import Path

from tracelens.domain.results import RequestTrace, TraceEvent
from tracelens.parsing.jsonl import ValidRecord, iter_jsonl


def find_request_trace(path: Path, request_id: str, *, strict: bool = False) -> RequestTrace | None:
    """Read a file again and return events matching one exact request ID."""
    if not request_id:
        raise ValueError("request_id must not be empty")
    events = [
        TraceEvent(
            timestamp=result.record.timestamp,
            service=result.record.service,
            method=result.record.method,
            path=result.record.path,
            status_code=result.record.status_code,
            duration_ms=result.record.duration_ms,
        )
        for result in iter_jsonl(path, strict=strict)
        if isinstance(result, ValidRecord) and result.record.request_id == request_id
    ]
    if not events:
        return None
    events.sort(key=lambda event: event.timestamp)
    return RequestTrace(
        request_id=request_id,
        events=events,
        total_events=len(events),
        flow_duration_ms=(events[-1].timestamp - events[0].timestamp).total_seconds() * 1_000,
        final_status_code=events[-1].status_code,
    )
