"""Unit tests for the root-cause correlation engine.

The engine reasons over the *contract* evidence records (``packages.contracts.evidence``): a signal is a
kind, an observation window and a bounded payload. These tests drive it with fixed timestamps so every
confidence assertion is deterministic, and they pin the behaviour an on-call engineer depends on: a
deployment inside the correlation window is suspicious, an old one is not, and an empty evidence set must
produce an explicit uncertainty rather than a guess.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from packages.contracts.common import Environment, ServiceRef
from packages.contracts.evidence import Evidence, EvidenceCollector, EvidenceKind, TimeWindow
from services.incident_agent.correlation import (
    CauseCategory,
    CorrelationResult,
    RootCauseCorrelator,
)

pytestmark = pytest.mark.unit

INCIDENT_ID = "INC-2026-0001"
CORRELATION_ID = "b6f1c0de-0001-4a11-9f6e-0123456789ab"
INCIDENT_START = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
SERVICE = ServiceRef(name="demo-api", environment=Environment.PRODUCTION, namespace="demo")
WINDOW = TimeWindow(start=INCIDENT_START - timedelta(minutes=30), end=INCIDENT_START)


def signal(
    evidence_id: str,
    kind: EvidenceKind,
    collected_at: datetime,
    *,
    summary: str = "Observed signal",
    payload: dict[str, Any] | None = None,
    collector: EvidenceCollector = EvidenceCollector.PLATFORM,
) -> Evidence:
    """Build one contract-valid evidence record for the correlator to reason over."""
    return Evidence(
        evidence_id=evidence_id,
        kind=kind,
        collector=collector,
        collected_at=collected_at,
        summary=summary,
        service=SERVICE,
        window=WINDOW,
        payload=payload if payload is not None else {},
        incident_id=INCIDENT_ID,
        correlation_id=CORRELATION_ID,
    )


def categories(result: CorrelationResult) -> list[CauseCategory]:
    """Return the categories of the suspected causes, highest confidence first."""
    return [cause.category for cause in result.suspected_causes]


def test_correlator_defaults_match_the_documented_window_and_threshold() -> None:
    """The defaults are part of the contract: 15 minutes and a 0.3 confidence floor."""
    correlator = RootCauseCorrelator()

    assert correlator.correlation_window == timedelta(minutes=15)
    assert correlator.min_confidence == 0.3


def test_recent_deployment_is_correlated_with_high_confidence() -> None:
    """A deployment two minutes before detection is the most likely trigger."""
    correlator = RootCauseCorrelator()

    deployment = signal(
        "EVD-2026-0001",
        EvidenceKind.DEPLOYMENT_EVENT,
        INCIDENT_START - timedelta(minutes=2),
        summary="Deployment of demo-api v1.2.4",
        payload={"version": "v1.2.4", "commit": "4a1b2c3d"},
        collector=EvidenceCollector.GITHUB,
    )

    result = correlator.correlate([deployment], INCIDENT_START)

    assert CauseCategory.DEPLOYMENT in categories(result)
    deployment_cause = next(
        cause for cause in result.suspected_causes if cause.category is CauseCategory.DEPLOYMENT
    )
    # 0.9 - (120 s / 900 s) = 0.7666...
    assert deployment_cause.confidence > 0.7
    assert deployment_cause.evidence_ids == ["EVD-2026-0001"]


def test_deployment_outside_the_correlation_window_is_not_correlated() -> None:
    """A release an hour before detection is history, not a cause."""
    correlator = RootCauseCorrelator(correlation_window=timedelta(minutes=5))

    deployment = signal(
        "EVD-2026-0002",
        EvidenceKind.DEPLOYMENT_EVENT,
        INCIDENT_START - timedelta(hours=1),
        summary="Old deployment",
        collector=EvidenceCollector.GITHUB,
    )

    result = correlator.correlate([deployment], INCIDENT_START)

    assert CauseCategory.DEPLOYMENT not in categories(result)


def test_pod_restarts_are_correlated_as_an_infrastructure_cause() -> None:
    """Restarts reported by the Kubernetes collector point at the platform, not the application."""
    correlator = RootCauseCorrelator()

    restart = signal(
        "EVD-2026-0003",
        EvidenceKind.KUBERNETES_OBJECT,
        INCIDENT_START - timedelta(minutes=1),
        summary="Pod restarts detected",
        payload={"restart_count": 5, "reason": "CrashLoopBackOff"},
        collector=EvidenceCollector.KUBERNETES,
    )

    result = correlator.correlate([restart], INCIDENT_START)

    assert CauseCategory.INFRASTRUCTURE in categories(result)


def test_database_errors_are_correlated() -> None:
    """A connection-pool timeout in the logs is a database cause."""
    correlator = RootCauseCorrelator()

    log = signal(
        "EVD-2026-0004",
        EvidenceKind.LOG_EXCERPT,
        INCIDENT_START - timedelta(seconds=30),
        summary="Database connection timeout",
        payload={"logs": ["ERROR: database connection timeout", "pg pool exhausted"]},
        collector=EvidenceCollector.OPENTELEMETRY_LOGS,
    )

    result = correlator.correlate([log], INCIDENT_START)

    assert CauseCategory.DATABASE in categories(result)


def test_cache_errors_are_correlated() -> None:
    """A refused Redis connection is a cache cause."""
    correlator = RootCauseCorrelator()

    log = signal(
        "EVD-2026-0005",
        EvidenceKind.LOG_EXCERPT,
        INCIDENT_START - timedelta(seconds=45),
        summary="Redis connection refused",
        payload={"logs": ["ERROR: redis connection refused", "cache unavailable"]},
        collector=EvidenceCollector.OPENTELEMETRY_LOGS,
    )

    result = correlator.correlate([log], INCIDENT_START)

    assert CauseCategory.CACHE in categories(result)


def test_application_errors_are_correlated() -> None:
    """An unhandled exception is an application cause."""
    correlator = RootCauseCorrelator()

    log = signal(
        "EVD-2026-0006",
        EvidenceKind.LOG_EXCERPT,
        INCIDENT_START - timedelta(minutes=1),
        summary="Unhandled exception in request handler",
        payload={"logs": ["Traceback (most recent call last)", "ValueError: failed to parse body"]},
        collector=EvidenceCollector.OPENTELEMETRY_LOGS,
    )

    result = correlator.correlate([log], INCIDENT_START)

    assert CauseCategory.APPLICATION_ERROR in categories(result)


def test_resource_exhaustion_is_correlated() -> None:
    """An OOM kill is resource exhaustion, whether it arrives as an event or a metric."""
    correlator = RootCauseCorrelator()

    event = signal(
        "EVD-2026-0007",
        EvidenceKind.KUBERNETES_OBJECT,
        INCIDENT_START - timedelta(seconds=20),
        summary="OOMKilled",
        payload={"reason": "OOMKilled", "memory_limit": "512Mi"},
        collector=EvidenceCollector.KUBERNETES,
    )

    result = correlator.correlate([event], INCIDENT_START)

    assert CauseCategory.RESOURCE_EXHAUSTION in categories(result)


def test_suspected_causes_are_sorted_by_descending_confidence() -> None:
    """The strongest hypothesis is always first, so a caller can act on the head of the list."""
    correlator = RootCauseCorrelator()

    recent_deployment = signal(
        "EVD-2026-0008",
        EvidenceKind.DEPLOYMENT_EVENT,
        INCIDENT_START - timedelta(minutes=1),
        summary="Recent deployment",
        collector=EvidenceCollector.GITHUB,
    )
    older_logs = signal(
        "EVD-2026-0009",
        EvidenceKind.LOG_EXCERPT,
        INCIDENT_START - timedelta(minutes=10),
        summary="Application errors",
        payload={"logs": ["error"]},
        collector=EvidenceCollector.OPENTELEMETRY_LOGS,
    )

    result = correlator.correlate([recent_deployment, older_logs], INCIDENT_START)

    confidences = [cause.confidence for cause in result.suspected_causes]
    assert confidences == sorted(confidences, reverse=True)
    assert result.suspected_causes[0].category is CauseCategory.DEPLOYMENT


def test_evidence_timeline_is_chronological() -> None:
    """The timeline is the record a reviewer reads, so it must be oldest first."""
    correlator = RootCauseCorrelator()

    late = signal(
        "EVD-2026-0010",
        EvidenceKind.LOG_EXCERPT,
        INCIDENT_START,
        payload={"logs": ["error"]},
    )
    early = signal(
        "EVD-2026-0011",
        EvidenceKind.DEPLOYMENT_EVENT,
        INCIDENT_START - timedelta(minutes=5),
    )

    result = correlator.correlate([late, early], INCIDENT_START)

    timestamps = [entry[0] for entry in result.evidence_timeline]
    assert timestamps == sorted(timestamps)
    assert [entry[1] for entry in result.evidence_timeline] == ["EVD-2026-0011", "EVD-2026-0010"]


def test_confidence_factors_are_bounded_probabilities() -> None:
    """Every reported factor is a probability in [0, 1], never a raw count."""
    correlator = RootCauseCorrelator()

    evidence_items = [
        signal(
            f"EVD-2026-10{index:02d}",
            kind,
            INCIDENT_START - timedelta(minutes=index + 1),
            payload={"logs": ["error"]},
        )
        for index, kind in enumerate([EvidenceKind.LOG_EXCERPT, EvidenceKind.METRIC_SERIES])
    ]

    result = correlator.correlate(evidence_items, INCIDENT_START)

    assert {"evidence_count", "evidence_diversity", "cause_agreement"} <= set(
        result.confidence_factors
    )
    assert all(0.0 <= value <= 1.0 for value in result.confidence_factors.values())


def test_weak_signal_is_reported_as_low_confidence() -> None:
    """A single weak signal is a hypothesis, and the result has to say so."""
    correlator = RootCauseCorrelator(min_confidence=0.0)

    weak_signal = signal(
        "EVD-2026-0012",
        EvidenceKind.LOG_EXCERPT,
        INCIDENT_START - timedelta(minutes=1),
        summary="One application error",
        payload={"logs": ["error"]},
        collector=EvidenceCollector.OPENTELEMETRY_LOGS,
    )

    result = correlator.correlate([weak_signal], INCIDENT_START)

    assert [cause.confidence for cause in result.suspected_causes] == [pytest.approx(0.4)]
    assert "Low confidence in all suspected causes" in result.unresolved_uncertainties


def test_evidence_older_than_the_window_does_not_produce_a_cause() -> None:
    """A signal from two hours ago cannot explain an incident detected now."""
    correlator = RootCauseCorrelator(min_confidence=0.0)

    stale_signal = signal(
        "EVD-2026-0013",
        EvidenceKind.LOG_EXCERPT,
        INCIDENT_START - timedelta(hours=2),
        summary="Old application error",
        payload={"logs": ["error"]},
        collector=EvidenceCollector.OPENTELEMETRY_LOGS,
    )

    result = correlator.correlate([stale_signal], INCIDENT_START)

    assert result.suspected_causes == []
    assert "Insufficient evidence to determine root cause" in result.unresolved_uncertainties


def test_empty_evidence_reports_insufficient_evidence() -> None:
    """With nothing to reason over, the engine must say so rather than invent a cause."""
    correlator = RootCauseCorrelator()

    result = correlator.correlate([], INCIDENT_START)

    assert result.suspected_causes == []
    assert "Insufficient evidence to determine root cause" in result.unresolved_uncertainties
    assert "No deployment history available" in result.unresolved_uncertainties
    assert "Limited log evidence" in result.unresolved_uncertainties
