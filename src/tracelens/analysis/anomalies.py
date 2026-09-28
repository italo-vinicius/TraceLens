"""Explainable statistical anomaly detection for timeline buckets."""

from statistics import fmean, pstdev
from typing import Literal

from tracelens.domain.results import Anomaly, TimelineBucket

BASELINE_WINDOW_COUNT = 10
MINIMUM_REQUEST_COUNT = 20


class AnomalyDetector:
    """Detect simple error-rate and latency spikes using rolling baselines."""

    def detect(self, timeline: list[TimelineBucket]) -> list[Anomaly]:
        """Evaluate each bucket after ten preceding populated buckets."""
        anomalies: list[Anomaly] = []
        for index, current in enumerate(timeline):
            history = timeline[max(0, index - BASELINE_WINDOW_COUNT) : index]
            if (
                len(history) < BASELINE_WINDOW_COUNT
                or current.request_count < MINIMUM_REQUEST_COUNT
            ):
                continue
            error_anomaly = self._error_rate_anomaly(current, history)
            if error_anomaly is not None:
                anomalies.append(error_anomaly)
            latency_anomaly = self._latency_anomaly(current, history)
            if latency_anomaly is not None:
                anomalies.append(latency_anomaly)
        return anomalies

    def _error_rate_anomaly(
        self, current: TimelineBucket, history: list[TimelineBucket]
    ) -> Anomaly | None:
        historical_rates = [bucket.error_rate for bucket in history]
        baseline = fmean(historical_rates)
        threshold = baseline + 3 * pstdev(historical_rates)
        if not (
            current.error_rate >= 0.05
            and current.error_rate > threshold
            and current.error_rate >= 2 * baseline
        ):
            return None
        severity: Literal["warning", "critical"] = (
            "critical" if current.error_rate >= 0.20 else "warning"
        )
        return Anomaly(
            started_at=current.started_at,
            finished_at=current.finished_at,
            type="error_rate_spike",
            severity=severity,
            observed_value=current.error_rate,
            reference_value=threshold,
            explanation=(
                f"Error rate of {current.error_rate:.1%} exceeds the rolling threshold "
                f"of {threshold:.1%} from the preceding ten windows."
            ),
        )

    def _latency_anomaly(
        self, current: TimelineBucket, history: list[TimelineBucket]
    ) -> Anomaly | None:
        if current.p95_ms is None:
            return None
        historical_p95 = [bucket.p95_ms for bucket in history if bucket.p95_ms is not None]
        if len(historical_p95) < BASELINE_WINDOW_COUNT:
            return None
        baseline = fmean(historical_p95)
        if not (current.p95_ms > 500 and current.p95_ms > 2 * baseline):
            return None
        severity: Literal["warning", "critical"] = (
            "critical" if current.p95_ms > 1_000 or current.p95_ms > 3 * baseline else "warning"
        )
        return Anomaly(
            started_at=current.started_at,
            finished_at=current.finished_at,
            type="latency_spike",
            severity=severity,
            observed_value=current.p95_ms,
            reference_value=baseline,
            explanation=(
                f"p95 latency of {current.p95_ms:.0f} ms is more than twice the rolling "
                f"baseline of {baseline:.0f} ms from the preceding ten windows."
            ),
        )
