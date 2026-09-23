"""Anomaly detection using deterministic methods.

This module provides telemetry anomaly detection using statistical methods
before introducing ML models. It focuses on:
- Rolling baseline comparison
- Threshold deviations
- Rate-of-change analysis
- Alert deduplication
- False-positive suppression
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
import logging
from typing import Any

logger = logging.getLogger(__name__)


class AnomalyType(StrEnum):
    """Type of detected anomaly."""

    THRESHOLD_BREACH = "threshold_breach"
    RATE_SPIKE = "rate_spike"
    RATE_DROP = "rate_drop"
    STATISTICAL_OUTLIER = "statistical_outlier"
    BASELINE_DEVIATION = "baseline_deviation"


class AnomalySeverity(StrEnum):
    """Severity level of anomaly."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TimeSeriesPoint:
    """A single metric data point."""

    timestamp: datetime
    value: float
    labels: dict[str, str]
    metric_name: str = ""


@dataclass
class Anomaly:
    """A detected anomaly."""

    anomaly_id: str
    metric_name: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    detected_at: datetime
    current_value: float
    expected_value: float | None
    deviation: float
    confidence: float
    context: dict[str, Any]
    suppressed: bool = False


@dataclass
class RollingBaseline:
    """Rolling baseline statistics for a metric."""

    metric_name: str
    window_size: int  # in data points
    values: list[float]
    mean: float = 0.0
    stddev: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    last_updated: datetime | None = None

    def update(self, value: float, timestamp: datetime) -> None:
        """Update baseline with new value."""
        self.values.append(value)

        # Keep only window_size most recent values
        if len(self.values) > self.window_size:
            self.values.pop(0)

        # Recalculate statistics
        if self.values:
            self.mean = sum(self.values) / len(self.values)
            self.min_value = min(self.values)
            self.max_value = max(self.values)

            # Calculate standard deviation
            if len(self.values) > 1:
                variance = sum((x - self.mean) ** 2 for x in self.values) / len(self.values)
                self.stddev = variance**0.5
            else:
                self.stddev = 0.0

        self.last_updated = timestamp


@dataclass
class ThresholdConfig:
    """Configuration for threshold-based detection."""

    metric_name: str
    upper_threshold: float | None = None
    lower_threshold: float | None = None
    rate_threshold: float | None = None  # Maximum rate of change per second
    enabled: bool = True


class AnomalyDetector:
    """Deterministic anomaly detector for telemetry data."""

    def __init__(
        self,
        baseline_window: int = 100,
        stddev_threshold: float = 3.0,
        rate_change_threshold: float = 0.5,
        correlation_window: timedelta = timedelta(minutes=5),
        min_confidence: float = 0.7,
    ) -> None:
        """Initialize anomaly detector.

        Parameters
        ----------
        baseline_window
            Number of data points for rolling baseline
        stddev_threshold
            Number of standard deviations for statistical outlier detection
        rate_change_threshold
            Fraction change per minute to trigger rate anomaly (0.5 = 50%)
        correlation_window
            Time window for correlating related anomalies
        min_confidence
            Minimum confidence threshold for reporting anomalies
        """
        self.baseline_window = baseline_window
        self.stddev_threshold = stddev_threshold
        self.rate_change_threshold = rate_change_threshold
        self.correlation_window = correlation_window
        self.min_confidence = min_confidence

        # State tracking
        self._baselines: dict[str, RollingBaseline] = {}
        self._thresholds: dict[str, ThresholdConfig] = {}
        self._recent_anomalies: list[Anomaly] = []
        self._last_values: dict[str, TimeSeriesPoint] = {}
        self._suppression_map: dict[str, set[str]] = defaultdict(set)

        logger.info(
            "Initialized anomaly detector: baseline_window=%d, stddev_threshold=%.1f",
            baseline_window,
            stddev_threshold,
        )

    def configure_threshold(self, config: ThresholdConfig) -> None:
        """Configure threshold for a metric.

        Parameters
        ----------
        config
            Threshold configuration
        """
        self._thresholds[config.metric_name] = config
        logger.info("Configured threshold for metric %s", config.metric_name)

    def detect(self, point: TimeSeriesPoint) -> list[Anomaly]:
        """Detect anomalies in a time series point.

        Parameters
        ----------
        point
            Time series data point

        Returns
        -------
        list[Anomaly]
            List of detected anomalies
        """
        anomalies: list[Anomaly] = []

        # Ensure baseline exists
        if point.metric_name not in self._baselines:
            self._baselines[point.metric_name] = RollingBaseline(
                metric_name=point.metric_name,
                window_size=self.baseline_window,
                values=[],
            )

        baseline = self._baselines[point.metric_name]

        # Check threshold breaches
        threshold_config = self._thresholds.get(point.metric_name)
        if threshold_config and threshold_config.enabled:
            threshold_anomaly = self._check_threshold(point, threshold_config)
            if threshold_anomaly:
                anomalies.append(threshold_anomaly)

        # Check statistical outliers (only if we have enough baseline data)
        if len(baseline.values) >= 10:
            outlier_anomaly = self._check_statistical_outlier(point, baseline)
            if outlier_anomaly:
                anomalies.append(outlier_anomaly)

        # Check rate of change
        if point.metric_name in self._last_values:
            rate_anomaly = self._check_rate_of_change(point, self._last_values[point.metric_name])
            if rate_anomaly:
                anomalies.append(rate_anomaly)

        # Update baseline after detection
        baseline.update(point.value, point.timestamp)

        # Store current value for next rate-of-change check
        self._last_values[point.metric_name] = point

        # Filter by confidence and apply suppression
        filtered_anomalies = []
        for anomaly in anomalies:
            if anomaly.confidence >= self.min_confidence:
                if not self._should_suppress(anomaly):
                    filtered_anomalies.append(anomaly)
                    self._recent_anomalies.append(anomaly)
                else:
                    anomaly.suppressed = True
                    filtered_anomalies.append(anomaly)

        # Cleanup old anomalies from correlation window
        self._cleanup_old_anomalies(point.timestamp)

        return filtered_anomalies

    def _check_threshold(self, point: TimeSeriesPoint, config: ThresholdConfig) -> Anomaly | None:
        """Check for threshold breaches."""
        if config.upper_threshold is not None and point.value > config.upper_threshold:
            deviation = (point.value - config.upper_threshold) / config.upper_threshold
            severity = self._calculate_severity(deviation)

            return Anomaly(
                anomaly_id=f"anomaly-{point.metric_name}-{point.timestamp.isoformat()}",
                metric_name=point.metric_name,
                anomaly_type=AnomalyType.THRESHOLD_BREACH,
                severity=severity,
                detected_at=point.timestamp,
                current_value=point.value,
                expected_value=config.upper_threshold,
                deviation=deviation,
                confidence=0.95,  # High confidence for explicit threshold
                context={
                    "threshold_type": "upper",
                    "threshold_value": config.upper_threshold,
                    "labels": point.labels,
                },
            )

        if config.lower_threshold is not None and point.value < config.lower_threshold:
            deviation = abs((point.value - config.lower_threshold) / config.lower_threshold)
            severity = self._calculate_severity(deviation)

            return Anomaly(
                anomaly_id=f"anomaly-{point.metric_name}-{point.timestamp.isoformat()}",
                metric_name=point.metric_name,
                anomaly_type=AnomalyType.THRESHOLD_BREACH,
                severity=severity,
                detected_at=point.timestamp,
                current_value=point.value,
                expected_value=config.lower_threshold,
                deviation=deviation,
                confidence=0.95,
                context={
                    "threshold_type": "lower",
                    "threshold_value": config.lower_threshold,
                    "labels": point.labels,
                },
            )

        return None

    def _check_statistical_outlier(
        self, point: TimeSeriesPoint, baseline: RollingBaseline
    ) -> Anomaly | None:
        """Check for statistical outliers using z-score."""
        if baseline.stddev == 0:
            return None

        z_score = abs(point.value - baseline.mean) / baseline.stddev

        if z_score > self.stddev_threshold:
            deviation = (
                abs(point.value - baseline.mean) / baseline.mean if baseline.mean != 0 else 0
            )
            severity = self._calculate_severity(deviation)

            return Anomaly(
                anomaly_id=f"anomaly-{point.metric_name}-{point.timestamp.isoformat()}",
                metric_name=point.metric_name,
                anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                severity=severity,
                detected_at=point.timestamp,
                current_value=point.value,
                expected_value=baseline.mean,
                deviation=deviation,
                confidence=min(0.9, z_score / (self.stddev_threshold * 2)),
                context={
                    "z_score": z_score,
                    "baseline_mean": baseline.mean,
                    "baseline_stddev": baseline.stddev,
                    "labels": point.labels,
                },
            )

        return None

    def _check_rate_of_change(
        self, current: TimeSeriesPoint, previous: TimeSeriesPoint
    ) -> Anomaly | None:
        """Check for rapid rate of change."""
        time_delta = (current.timestamp - previous.timestamp).total_seconds()
        if time_delta == 0:
            return None

        # Calculate rate per minute
        value_change = abs(current.value - previous.value)
        rate_per_minute = (value_change / time_delta) * 60

        # Calculate fractional change
        if previous.value != 0:
            fractional_change = value_change / abs(previous.value)
        else:
            fractional_change = 0 if value_change == 0 else 1.0

        if fractional_change > self.rate_change_threshold:
            severity = self._calculate_severity(fractional_change)
            anomaly_type = (
                AnomalyType.RATE_SPIKE if current.value > previous.value else AnomalyType.RATE_DROP
            )

            return Anomaly(
                anomaly_id=f"anomaly-{current.metric_name}-{current.timestamp.isoformat()}",
                metric_name=current.metric_name,
                anomaly_type=anomaly_type,
                severity=severity,
                detected_at=current.timestamp,
                current_value=current.value,
                expected_value=previous.value,
                deviation=fractional_change,
                confidence=0.85,
                context={
                    "rate_per_minute": rate_per_minute,
                    "previous_value": previous.value,
                    "time_delta_seconds": time_delta,
                    "labels": current.labels,
                },
            )

        return None

    def _calculate_severity(self, deviation: float) -> AnomalySeverity:
        """Calculate severity based on deviation magnitude."""
        if deviation >= 1.0:  # 100% or more
            return AnomalySeverity.CRITICAL
        if deviation >= 0.5:  # 50-100%
            return AnomalySeverity.HIGH
        if deviation >= 0.2:  # 20-50%
            return AnomalySeverity.MEDIUM
        return AnomalySeverity.LOW

    def _should_suppress(self, anomaly: Anomaly) -> bool:
        """Determine if anomaly should be suppressed due to recent similar detections.

        This implements alert deduplication: if we've recently reported a similar
        anomaly for the same metric, suppress this one to avoid alert fatigue.
        """
        # Check for recent similar anomalies
        for recent in self._recent_anomalies:
            if (
                recent.metric_name == anomaly.metric_name
                and recent.anomaly_type == anomaly.anomaly_type
                and (anomaly.detected_at - recent.detected_at) < self.correlation_window
            ):
                # Similar anomaly detected recently - suppress this one
                logger.debug(
                    "Suppressing anomaly for %s (similar to %s)",
                    anomaly.anomaly_id,
                    recent.anomaly_id,
                )
                return True

        return False

    def _cleanup_old_anomalies(self, current_time: datetime) -> None:
        """Remove anomalies outside correlation window."""
        cutoff = current_time - self.correlation_window
        self._recent_anomalies = [a for a in self._recent_anomalies if a.detected_at >= cutoff]

    def correlate_anomalies(
        self, anomalies: list[Anomaly], window: timedelta | None = None
    ) -> list[list[Anomaly]]:
        """Correlate related anomalies within a time window.

        Groups anomalies that occurred close together in time, which may
        indicate a common root cause.

        Parameters
        ----------
        anomalies
            List of anomalies to correlate
        window
            Time window for correlation (uses instance default if None)

        Returns
        -------
        list[list[Anomaly]]
            Groups of correlated anomalies
        """
        if not anomalies:
            return []

        window = window or self.correlation_window

        # Sort by timestamp
        sorted_anomalies = sorted(anomalies, key=lambda a: a.detected_at)

        # Group anomalies within time window
        groups: list[list[Anomaly]] = []
        current_group: list[Anomaly] = [sorted_anomalies[0]]

        for anomaly in sorted_anomalies[1:]:
            time_diff = anomaly.detected_at - current_group[-1].detected_at

            if time_diff <= window:
                current_group.append(anomaly)
            else:
                groups.append(current_group)
                current_group = [anomaly]

        if current_group:
            groups.append(current_group)

        logger.info("Correlated %d anomalies into %d groups", len(anomalies), len(groups))

        return groups

    def get_baseline_stats(self, metric_name: str) -> dict[str, Any]:
        """Get current baseline statistics for a metric.

        Parameters
        ----------
        metric_name
            Metric name

        Returns
        -------
        dict[str, Any]
            Baseline statistics
        """
        baseline = self._baselines.get(metric_name)
        if not baseline:
            return {"error": "No baseline available"}

        return {
            "metric_name": baseline.metric_name,
            "window_size": baseline.window_size,
            "data_points": len(baseline.values),
            "mean": baseline.mean,
            "stddev": baseline.stddev,
            "min": baseline.min_value,
            "max": baseline.max_value,
            "last_updated": baseline.last_updated.isoformat() if baseline.last_updated else None,
        }
