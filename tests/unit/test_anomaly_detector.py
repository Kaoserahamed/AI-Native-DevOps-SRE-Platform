"""Unit tests for anomaly detector."""

import pytest
from datetime import datetime, timedelta

from services.anomaly_agent.detector import (
    AnomalyDetector,
    AnomalyType,
    AnomalySeverity,
    TimeSeriesPoint,
    ThresholdConfig,
    RollingBaseline,
)


class TestRollingBaseline:
    """Test rolling baseline calculations."""

    def test_baseline_initialization(self):
        """Test baseline starts empty."""
        baseline = RollingBaseline(metric_name="test_metric", window_size=100, values=[])
        
        assert baseline.metric_name == "test_metric"
        assert baseline.window_size == 100
        assert len(baseline.values) == 0
        assert baseline.mean == 0.0
        assert baseline.stddev == 0.0

    def test_baseline_update_single_value(self):
        """Test baseline with single value."""
        baseline = RollingBaseline(metric_name="test", window_size=10, values=[])
        baseline.update(5.0, datetime.now())
        
        assert len(baseline.values) == 1
        assert baseline.mean == 5.0
        assert baseline.stddev == 0.0
        assert baseline.min_value == 5.0
        assert baseline.max_value == 5.0

    def test_baseline_update_multiple_values(self):
        """Test baseline statistics with multiple values."""
        baseline = RollingBaseline(metric_name="test", window_size=10, values=[])
        
        for value in [1.0, 2.0, 3.0, 4.0, 5.0]:
            baseline.update(value, datetime.now())
        
        assert len(baseline.values) == 5
        assert baseline.mean == 3.0
        assert baseline.min_value == 1.0
        assert baseline.max_value == 5.0
        assert baseline.stddev > 0  # Should have variance

    def test_baseline_window_limit(self):
        """Test baseline respects window size."""
        baseline = RollingBaseline(metric_name="test", window_size=3, values=[])
        
        for i in range(10):
            baseline.update(float(i), datetime.now())
        
        assert len(baseline.values) == 3  # Should only keep last 3
        assert baseline.values == [7.0, 8.0, 9.0]


class TestAnomalyDetector:
    """Test anomaly detection logic."""

    def test_detector_initialization(self):
        """Test detector initializes with defaults."""
        detector = AnomalyDetector()
        
        assert detector.baseline_window == 100
        assert detector.stddev_threshold == 3.0
        assert detector.min_confidence == 0.7

    def test_threshold_breach_detection_upper(self):
        """Test detection of upper threshold breach."""
        detector = AnomalyDetector()
        detector.configure_threshold(
            ThresholdConfig(
                metric_name="error_rate",
                upper_threshold=0.05,
                enabled=True,
            )
        )
        
        point = TimeSeriesPoint(
            timestamp=datetime.now(),
            value=0.10,  # Above threshold
            labels={"service": "test"},
            metric_name="error_rate",
        )
        
        anomalies = detector.detect(point)
        
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.THRESHOLD_BREACH
        assert anomalies[0].current_value == 0.10
        assert anomalies[0].expected_value == 0.05
        assert anomalies[0].confidence >= 0.9

    def test_threshold_breach_detection_lower(self):
        """Test detection of lower threshold breach."""
        detector = AnomalyDetector()
        detector.configure_threshold(
            ThresholdConfig(
                metric_name="availability",
                lower_threshold=0.99,
                enabled=True,
            )
        )
        
        point = TimeSeriesPoint(
            timestamp=datetime.now(),
            value=0.95,  # Below threshold
            labels={"service": "test"},
            metric_name="availability",
        )
        
        anomalies = detector.detect(point)
        
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.THRESHOLD_BREACH
        assert anomalies[0].current_value == 0.95

    def test_no_detection_within_threshold(self):
        """Test no anomaly when value is within threshold."""
        detector = AnomalyDetector()
        detector.configure_threshold(
            ThresholdConfig(
                metric_name="error_rate",
                upper_threshold=0.05,
                enabled=True,
            )
        )
        
        point = TimeSeriesPoint(
            timestamp=datetime.now(),
            value=0.03,  # Below threshold
            labels={"service": "test"},
            metric_name="error_rate",
        )
        
        anomalies = detector.detect(point)
        
        # Might have other anomalies, but not threshold breach
        threshold_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.THRESHOLD_BREACH]
        assert len(threshold_anomalies) == 0

    def test_statistical_outlier_detection(self):
        """Test z-score based outlier detection."""
        detector = AnomalyDetector(stddev_threshold=2.0)
        
        # Build baseline with normal values
        base_time = datetime.now()
        for i in range(20):
            point = TimeSeriesPoint(
                timestamp=base_time + timedelta(seconds=i),
                value=100.0,  # Stable baseline
                labels={},
                metric_name="latency",
            )
            detector.detect(point)
        
        # Now send an outlier
        outlier_point = TimeSeriesPoint(
            timestamp=base_time + timedelta(seconds=21),
            value=500.0,  # 5x the baseline
            labels={},
            metric_name="latency",
        )
        
        anomalies = detector.detect(outlier_point)
        
        outlier_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.STATISTICAL_OUTLIER]
        assert len(outlier_anomalies) >= 1
        assert outlier_anomalies[0].current_value == 500.0

    def test_rate_of_change_detection_spike(self):
        """Test rate-of-change spike detection."""
        detector = AnomalyDetector(rate_change_threshold=0.3)
        
        base_time = datetime.now()
        
        # First point establishes baseline
        point1 = TimeSeriesPoint(
            timestamp=base_time,
            value=100.0,
            labels={},
            metric_name="requests_per_second",
        )
        detector.detect(point1)
        
        # Second point is 2x higher
        point2 = TimeSeriesPoint(
            timestamp=base_time + timedelta(seconds=1),
            value=200.0,  # 100% increase
            labels={},
            metric_name="requests_per_second",
        )
        
        anomalies = detector.detect(point2)
        
        rate_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.RATE_SPIKE]
        assert len(rate_anomalies) >= 1

    def test_rate_of_change_detection_drop(self):
        """Test rate-of-change drop detection."""
        detector = AnomalyDetector(rate_change_threshold=0.5)
        
        base_time = datetime.now()
        
        # High baseline
        point1 = TimeSeriesPoint(
            timestamp=base_time,
            value=1000.0,
            labels={},
            metric_name="active_connections",
        )
        detector.detect(point1)
        
        # Sudden drop to near zero
        point2 = TimeSeriesPoint(
            timestamp=base_time + timedelta(seconds=1),
            value=100.0,  # 90% decrease
            labels={},
            metric_name="active_connections",
        )
        
        anomalies = detector.detect(point2)
        
        rate_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.RATE_DROP]
        assert len(rate_anomalies) >= 1

    def test_confidence_threshold_filtering(self):
        """Test that low-confidence anomalies are filtered."""
        detector = AnomalyDetector(min_confidence=0.95)
        
        # Configure a threshold that will trigger medium confidence
        detector.configure_threshold(
            ThresholdConfig(
                metric_name="test_metric",
                upper_threshold=100.0,
                enabled=True,
            )
        )
        
        # Small breach (low confidence)
        point = TimeSeriesPoint(
            timestamp=datetime.now(),
            value=105.0,  # Just 5% over
            labels={},
            metric_name="test_metric",
        )
        
        anomalies = detector.detect(point)
        
        # Should be filtered due to min_confidence
        assert all(a.confidence >= 0.95 for a in anomalies)

    def test_alert_deduplication(self):
        """Test that similar anomalies are suppressed."""
        detector = AnomalyDetector(correlation_window=timedelta(minutes=5))
        detector.configure_threshold(
            ThresholdConfig(
                metric_name="error_rate",
                upper_threshold=0.01,
                enabled=True,
            )
        )
        
        base_time = datetime.now()
        
        # First anomaly
        point1 = TimeSeriesPoint(
            timestamp=base_time,
            value=0.10,
            labels={},
            metric_name="error_rate",
        )
        anomalies1 = detector.detect(point1)
        assert len([a for a in anomalies1 if not a.suppressed]) >= 1
        
        # Similar anomaly shortly after (should be suppressed)
        point2 = TimeSeriesPoint(
            timestamp=base_time + timedelta(seconds=30),
            value=0.11,
            labels={},
            metric_name="error_rate",
        )
        anomalies2 = detector.detect(point2)
        
        # Should be suppressed
        threshold_anomalies = [a for a in anomalies2 if a.anomaly_type == AnomalyType.THRESHOLD_BREACH]
        if threshold_anomalies:
            assert threshold_anomalies[0].suppressed

    def test_severity_calculation(self):
        """Test severity is calculated based on deviation magnitude."""
        detector = AnomalyDetector()
        detector.configure_threshold(
            ThresholdConfig(
                metric_name="latency",
                upper_threshold=100.0,
                enabled=True,
            )
        )
        
        # Critical severity (2x over threshold)
        critical_point = TimeSeriesPoint(
            timestamp=datetime.now(),
            value=300.0,
            labels={},
            metric_name="latency",
        )
        critical_anomalies = detector.detect(critical_point)
        critical_breach = [a for a in critical_anomalies if a.anomaly_type == AnomalyType.THRESHOLD_BREACH]
        if critical_breach:
            assert critical_breach[0].severity == AnomalySeverity.CRITICAL

    def test_correlate_anomalies(self):
        """Test anomaly correlation grouping."""
        detector = AnomalyDetector()
        
        base_time = datetime.now()
        
        anomalies = [
            TimeSeriesPoint(
                timestamp=base_time,
                value=100.0,
                labels={},
                metric_name=f"metric{i}",
            )
            for i in range(5)
        ]
        
        # Convert to anomaly objects for testing
        from services.anomaly_agent.detector import Anomaly
        anomaly_objects = [
            Anomaly(
                anomaly_id=f"anom-{i}",
                metric_name=f"metric{i}",
                anomaly_type=AnomalyType.THRESHOLD_BREACH,
                severity=AnomalySeverity.HIGH,
                detected_at=base_time + timedelta(seconds=i * 10),
                current_value=100.0,
                expected_value=50.0,
                deviation=1.0,
                confidence=0.9,
                context={},
            )
            for i in range(5)
        ]
        
        # Correlate with 30-second window
        groups = detector.correlate_anomalies(
            anomaly_objects,
            window=timedelta(seconds=30),
        )
        
        # First 3 should be in one group (0s, 10s, 20s)
        # Last 2 should be in another (30s, 40s)
        assert len(groups) == 2

    def test_baseline_stats_retrieval(self):
        """Test baseline statistics can be retrieved."""
        detector = AnomalyDetector()
        
        # Build some baseline
        for i in range(10):
            point = TimeSeriesPoint(
                timestamp=datetime.now(),
                value=float(i),
                labels={},
                metric_name="test_metric",
            )
            detector.detect(point)
        
        stats = detector.get_baseline_stats("test_metric")
        
        assert stats["metric_name"] == "test_metric"
        assert stats["data_points"] == 10
        assert "mean" in stats
        assert "stddev" in stats
        assert "min" in stats
        assert "max" in stats

    def test_baseline_stats_missing_metric(self):
        """Test baseline stats for nonexistent metric."""
        detector = AnomalyDetector()
        
        stats = detector.get_baseline_stats("nonexistent")
        
        assert "error" in stats
