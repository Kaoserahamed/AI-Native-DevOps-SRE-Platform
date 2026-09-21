"""Unit tests for root cause correlation engine."""

import pytest
from datetime import datetime, timedelta, UTC

from services.incident_agent.correlation import (
    RootCauseCorrelator,
    CauseCategory,
    SuspectedCause,
)
from packages.contracts.evidence import Evidence, EvidenceKind, Collector


class TestRootCauseCorrelator:
    """Test root cause correlation logic."""

    def test_correlator_initialization(self):
        """Test correlator initializes with defaults."""
        correlator = RootCauseCorrelator()
        
        assert correlator.correlation_window == timedelta(minutes=15)
        assert correlator.min_confidence == 0.3

    def test_correlate_deployment_cause(self):
        """Test correlation with recent deployment."""
        correlator = RootCauseCorrelator()
        
        incident_start = datetime.now(tz=UTC)
        deploy_time = incident_start - timedelta(minutes=2)
        
        # Create deployment evidence
        deployment_evidence = Evidence(
            evidence_id="EV-DEPLOY-001",
            incident_id="INC-001",
            kind=EvidenceKind.DEPLOYMENT,
            collector=Collector.GITHUB,
            collected_at=deploy_time,
            time_range_start=deploy_time,
            time_range_end=deploy_time,
            summary="Deployment of v1.2.4",
            data={"version": "v1.2.4", "commit": "abc123"},
        )
        
        result = correlator.correlate([deployment_evidence], incident_start)
        
        assert len(result.suspected_causes) >= 1
        deployment_causes = [c for c in result.suspected_causes if c.category == CauseCategory.DEPLOYMENT]
        assert len(deployment_causes) >= 1
        assert deployment_causes[0].confidence > 0.7  # Recent deployment = high confidence

    def test_correlate_pod_restart_cause(self):
        """Test correlation with pod restarts."""
        correlator = RootCauseCorrelator()
        
        incident_start = datetime.now(tz=UTC)
        restart_time = incident_start - timedelta(minutes=1)
        
        # Create pod restart evidence
        k8s_evidence = Evidence(
            evidence_id="EV-K8S-001",
            incident_id="INC-001",
            kind=EvidenceKind.KUBERNETES,
            collector=Collector.KUBECTL,
            collected_at=restart_time,
            time_range_start=restart_time,
            time_range_end=restart_time,
            summary="Pod restarts detected",
            data={"restart_count": 5, "reason": "CrashLoopBackOff"},
        )
        
        result = correlator.correlate([k8s_evidence], incident_start)
        
        infrastructure_causes = [c for c in result.suspected_causes if c.category == CauseCategory.INFRASTRUCTURE]
        assert len(infrastructure_causes) >= 1

    def test_correlate_database_errors(self):
        """Test correlation with database errors."""
        correlator = RootCauseCorrelator()
        
        incident_start = datetime.now(tz=UTC)
        error_time = incident_start - timedelta(seconds=30)
        
        # Create log evidence with database errors
        log_evidence = Evidence(
            evidence_id="EV-LOG-001",
            incident_id="INC-001",
            kind=EvidenceKind.LOG,
            collector=Collector.LOKI,
            collected_at=error_time,
            time_range_start=error_time,
            time_range_end=error_time,
            summary="Database connection timeout",
            data={"logs": ["ERROR: database connection timeout", "PostgreSQL connection pool exhausted"]},
        )
        
        result = correlator.correlate([log_evidence], incident_start)
        
        db_causes = [c for c in result.suspected_causes if c.category == CauseCategory.DATABASE]
        assert len(db_causes) >= 1

    def test_correlate_redis_errors(self):
        """Test correlation with Redis errors."""
        correlator = RootCauseCorrelator()
        
        incident_start = datetime.now(tz=UTC)
        error_time = incident_start - timedelta(seconds=45)
        
        # Create log evidence with Redis errors
        log_evidence = Evidence(
            evidence_id="EV-LOG-002",
            incident_id="INC-001",
            kind=EvidenceKind.LOG,
            collector=Collector.LOKI,
            collected_at=error_time,
            time_range_start=error_time,
            time_range_end=error_time,
            summary="Redis connection refused",
            data={"logs": ["ERROR: Redis connection refused", "Cache unavailable"]},
        )
        
        result = correlator.correlate([log_evidence], incident_start)
        
        cache_causes = [c for c in result.suspected_causes if c.category == CauseCategory.CACHE]
        assert len(cache_causes) >= 1

    def test_correlate_application_errors(self):
        """Test correlation with application errors."""
        correlator = RootCauseCorrelator()
        
        incident_start = datetime.now(tz=UTC)
        error_time = incident_start - timedelta(minutes=1)
        
        # Create log evidence with application errors
        log_evidence = Evidence(
            evidence_id="EV-LOG-003",
            incident_id="INC-001",
            kind=EvidenceKind.LOG,
            collector=Collector.LOKI,
            collected_at=error_time,
            time_range_start=error_time,
            time_range_end=error_time,
            summary="Application exception",
            data={"logs": ["ERROR: NullPointerException", "Traceback: ...", "Failed to process request"]},
        )
        
        result = correlator.correlate([log_evidence], incident_start)
        
        app_causes = [c for c in result.suspected_causes if c.category == CauseCategory.APPLICATION_ERROR]
        assert len(app_causes) >= 1

    def test_correlate_resource_exhaustion(self):
        """Test correlation with resource exhaustion."""
        correlator = RootCauseCorrelator()
        
        incident_start = datetime.now(tz=UTC)
        oom_time = incident_start - timedelta(seconds=20)
        
        # Create evidence with OOM
        k8s_evidence = Evidence(
            evidence_id="EV-K8S-002",
            incident_id="INC-001",
            kind=EvidenceKind.KUBERNETES,
            collector=Collector.KUBECTL,
            collected_at=oom_time,
            time_range_start=oom_time,
            time_range_end=oom_time,
            summary="OOMKilled",
            data={"reason": "OOMKilled", "memory_limit": "512Mi"},
        )
        
        result = correlator.correlate([k8s_evidence], incident_start)
        
        resource_causes = [c for c in result.suspected_causes if c.category == CauseCategory.RESOURCE_EXHAUSTION]
        assert len(resource_causes) >= 1

    def test_multiple_causes_sorted_by_confidence(self):
        """Test that multiple causes are sorted by confidence."""
        correlator = RootCauseCorrelator()
        
        incident_start = datetime.now(tz=UTC)
        
        # Create multiple evidence items
        deployment_evidence = Evidence(
            evidence_id="EV-DEPLOY-001",
            incident_id="INC-001",
            kind=EvidenceKind.DEPLOYMENT,
            collector=Collector.GITHUB,
            collected_at=incident_start - timedelta(minutes=1),  # Very recent
            time_range_start=incident_start - timedelta(minutes=1),
            time_range_end=incident_start - timedelta(minutes=1),
            summary="Recent deployment",
            data={},
        )
        
        log_evidence = Evidence(
            evidence_id="EV-LOG-001",
            incident_id="INC-001",
            kind=EvidenceKind.LOG,
            collector=Collector.LOKI,
            collected_at=incident_start - timedelta(minutes=10),  # Less recent
            time_range_start=incident_start - timedelta(minutes=10),
            time_range_end=incident_start - timedelta(minutes=10),
            summary="Some errors",
            data={"logs": ["error"]},
        )
        
        result = correlator.correlate([deployment_evidence, log_evidence], incident_start)
        
        # Should have multiple causes
        assert len(result.suspected_causes) >= 1
        
        # Should be sorted by confidence (highest first)
        confidences = [c.confidence for c in result.suspected_causes]
        assert confidences == sorted(confidences, reverse=True)

    def test_min_confidence_filtering(self):
        """Test that causes below min confidence are filtered."""
        correlator = RootCauseCorrelator(min_confidence=0.8)
        
        incident_start = datetime.now(tz=UTC)
        
        # Create evidence that would generate low confidence
        old_log = Evidence(
            evidence_id="EV-LOG-001",
            incident_id="INC-001",
            kind=EvidenceKind.LOG,
            collector=Collector.LOKI,
            collected_at=incident_start - timedelta(hours=1),  # Old evidence
            time_range_start=incident_start - timedelta(hours=1),
            time_range_end=incident_start - timedelta(hours=1),
            summary="Old error",
            data={"logs": ["error"]},
        )
        
        result = correlator.correlate([old_log], incident_start)
        
        # All returned causes should meet minimum confidence
        assert all(c.confidence >= 0.8 for c in result.suspected_causes)

    def test_evidence_timeline_construction(self):
        """Test that evidence timeline is built correctly."""
        correlator = RootCauseCorrelator()
        
        incident_start = datetime.now(tz=UTC)
        
        evidence_items = [
            Evidence(
                evidence_id=f"EV-{i}",
                incident_id="INC-001",
                kind=EvidenceKind.LOG,
                collector=Collector.LOKI,
                collected_at=incident_start - timedelta(minutes=i),
                time_range_start=incident_start - timedelta(minutes=i),
                time_range_end=incident_start - timedelta(minutes=i),
                summary=f"Event {i}",
                data={},
            )
            for i in range(5)
        ]
        
        result = correlator.correlate(evidence_items, incident_start)
        
        # Timeline should be sorted chronologically
        timeline = result.evidence_timeline
        assert len(timeline) == 5
        
        # Check chronological order (oldest first)
        timestamps = [t[0] for t in timeline]
        assert timestamps == sorted(timestamps)

    def test_uncertainty_identification_no_evidence(self):
        """Test uncertainty is flagged when evidence is insufficient."""
        correlator = RootCauseCorrelator()
        
        incident_start = datetime.now(tz=UTC)
        
        # No evidence
        result = correlator.correlate([], incident_start)
        
        assert "Insufficient evidence" in result.unresolved_uncertainties

    def test_uncertainty_identification_low_confidence(self):
        """Test uncertainty is flagged when all causes have low confidence."""
        correlator = RootCauseCorrelator(min_confidence=0.0)  # Don't filter
        
        incident_start = datetime.now(tz=UTC)
        
        # Create weak evidence (old)
        old_evidence = Evidence(
            evidence_id="EV-OLD",
            incident_id="INC-001",
            kind=EvidenceKind.LOG,
            collector=Collector.LOKI,
            collected_at=incident_start - timedelta(hours=2),
            time_range_start=incident_start - timedelta(hours=2),
            time_range_end=incident_start - timedelta(hours=2),
            summary="Old event",
            data={"logs": ["something"]},
        )
        
        result = correlator.correlate([old_evidence], incident_start)
        
        # Should flag low confidence
        assert any("Low confidence" in u for u in result.unresolved_uncertainties)

    def test_confidence_factors_calculation(self):
        """Test confidence factors are calculated."""
        correlator = RootCauseCorrelator()
        
        incident_start = datetime.now(tz=UTC)
        
        evidence_items = [
            Evidence(
                evidence_id=f"EV-{kind.value}",
                incident_id="INC-001",
                kind=kind,
                collector=Collector.LOKI,
                collected_at=incident_start,
                time_range_start=incident_start,
                time_range_end=incident_start,
                summary="Event",
                data={},
            )
            for kind in [EvidenceKind.LOG, EvidenceKind.METRIC, EvidenceKind.TRACE]
        ]
        
        result = correlator.correlate(evidence_items, incident_start)
        
        factors = result.confidence_factors
        assert "evidence_count" in factors
        assert "evidence_diversity" in factors
        assert all(0 <= v <= 1 for v in factors.values())

    def test_correlation_window_enforcement(self):
        """Test events outside correlation window are not correlated."""
        correlator = RootCauseCorrelator(correlation_window=timedelta(minutes=5))
        
        incident_start = datetime.now(tz=UTC)
        
        # Evidence outside window
        old_deployment = Evidence(
            evidence_id="EV-OLD-DEPLOY",
            incident_id="INC-001",
            kind=EvidenceKind.DEPLOYMENT,
            collector=Collector.GITHUB,
            collected_at=incident_start - timedelta(hours=1),  # Way before window
            time_range_start=incident_start - timedelta(hours=1),
            time_range_end=incident_start - timedelta(hours=1),
            summary="Old deployment",
            data={},
        )
        
        result = correlator.correlate([old_deployment], incident_start)
        
        # Should not find deployment correlation (outside window)
        deployment_causes = [c for c in result.suspected_causes if c.category == CauseCategory.DEPLOYMENT]
        assert len(deployment_causes) == 0

    def test_empty_evidence_returns_uncertainties(self):
        """Test that empty evidence list returns appropriate uncertainties."""
        correlator = RootCauseCorrelator()
        
        incident_start = datetime.now(tz=UTC)
        
        result = correlator.correlate([], incident_start)
        
        assert len(result.suspected_causes) == 0
        assert len(result.unresolved_uncertainties) > 0
        assert "Insufficient evidence" in result.unresolved_uncertainties
