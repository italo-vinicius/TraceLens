"""JSON serialization for analysis results."""

from pathlib import Path
from typing import Any

import orjson

from tracelens.domain.results import AnalysisResult


def _round_floats(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        return {key: _round_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_round_floats(item) for item in value]
    return value


def write_json_report(result: AnalysisResult, output: Path) -> None:
    """Write the versioned analysis contract as readable JSON."""
    payload = _round_floats(result.model_dump(mode="json"))
    output.write_bytes(
        orjson.dumps(payload, option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE)
    )
