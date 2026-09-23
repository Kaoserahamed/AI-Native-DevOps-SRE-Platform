"""Root cause correlation engine.

Correlates evidence from multiple sources to identify probable root causes:
- Deployment events
- Pod restarts
- Application errors
- Latency changes
- Database errors
- Redis errors
- Infrastructure events
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
import logging
from typing import Any

from packages.contracts.evidence import Evidence, EvidenceKind

logger = logging.getLogger(__name__)


class CauseCategory(StrEnum):
    """Category of suspected root cause."""

    DEPLOYMENT = "deployment"
    INFRASTRUCTURE = "infrastructure"
    DATABASE = "database"
    CACHE = "cache"
    NETWORK = "network"
    APPLICATION_ERROR = "application_error"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CONFIGURATION = "configuration"
    EXTERNAL_DEPENDENCY = "external_dependency"
    UNKNOWN = "unknown"


@dataclass
class SuspectedCause:
    """A suspected root cause with supporting evidence."""

    cause_id: str
    category: CauseCategory
    description: str
    confidence: float  # 0.0 to 1.0
    evidence_ids: list[str]
    evidence_summary: dict[str, Any]
    first_seen: datetime
    correlation_score: float
    uncertainty: str | None = None


@dataclass
class CorrelationResult:
    """Result of root cause correlation analysis."""

    suspected_causes: list[SuspectedCause]
    evidence_timeline: list[tuple[datetime, str, str]]  # timestamp, evidence_id, summary
    confidence_factors: dict[str, float]
    unresolved_uncertainties: list[str]


class RootCauseCorrelator:
    """Correlate evidence to identify probable root causes."""

    def __init__(
        self,
        correlation_window: timedelta = timedelta(minutes=15),
        min_confidence: float = 0.3,
    ) -> None:
        """Initialize root cause correlator.

        Parameters
        ----------
        correlation_window
            Time window for correlating events
        min_confidence
            Minimum confidence threshold for reporting causes
        """
        self.correlation_window = correlation_window
        self.min_confidence = min_confidence

        logger.info(
            "Initialized root cause correlator: correlation_window=%s, min_confidence=%.2f",
            correlation_window,
            min_confidence,
        )

    def correlate(
        self,
        evidence_list: list[Evidence],
        incident_start: datetime,
    ) -> CorrelationResult:
        """Correlate evidence to identify root causes.

        Parameters
        ----------
        evidence_list
            All evidence collected for the incident
        incident_start
            When the incident was first detected

        Returns
        -------
        CorrelationResult
            Suspected causes with confidence scores
        """
        logger.info("Correlating %d evidence items for incident", len(evidence_list))

        # Build timeline
        timeline = self._build_timeline(evidence_list)

        # Group evidence by type
        evidence_by_kind = self._group_evidence_by_kind(evidence_list)

        # Analyze different correlation patterns
        suspected_causes: list[SuspectedCause] = []
        uncertainties: list[str] = []

        # Pattern 1: Recent deployment correlation
        deployment_cause = self._correlate_deployment(evidence_by_kind, incident_start)
        if deployment_cause:
            suspected_causes.append(deployment_cause)

        # Pattern 2: Pod restart correlation
        pod_restart_cause = self._correlate_pod_restarts(evidence_by_kind, incident_start)
        if pod_restart_cause:
            suspected_causes.append(pod_restart_cause)

        # Pattern 3: Database error correlation
        database_cause = self._correlate_database_errors(evidence_by_kind, incident_start)
        if database_cause:
            suspected_causes.append(database_cause)

        # Pattern 4: Redis error correlation
        redis_cause = self._correlate_redis_errors(evidence_by_kind, incident_start)
        if redis_cause:
            suspected_causes.append(redis_cause)

        # Pattern 5: Application error correlation
        app_error_cause = self._correlate_application_errors(evidence_by_kind, incident_start)
        if app_error_cause:
            suspected_causes.append(app_error_cause)

        # Pattern 6: Resource exhaustion
        resource_cause = self._correlate_resource_exhaustion(evidence_by_kind, incident_start)
        if resource_cause:
            suspected_causes.append(resource_cause)

        # Filter by confidence threshold
        suspected_causes = [
            cause for cause in suspected_causes if cause.confidence >= self.min_confidence
        ]

        # Sort by confidence (highest first)
        suspected_causes.sort(key=lambda c: c.confidence, reverse=True)

        # Calculate confidence factors
        confidence_factors = self._calculate_confidence_factors(suspected_causes, evidence_list)

        # Identify unresolved uncertainties
        if not suspected_causes:
            uncertainties.append("Insufficient evidence to determine root cause")
        elif all(cause.confidence < 0.7 for cause in suspected_causes):
            uncertainties.append("Low confidence in all suspected causes")

        if not evidence_by_kind.get(EvidenceKind.DEPLOYMENT_EVENT):
            uncertainties.append("No deployment history available")

        if not evidence_by_kind.get(EvidenceKind.LOG_EXCERPT):
            uncertainties.append("Limited log evidence")

        logger.info(
            "Correlation complete: %d suspected causes, %d uncertainties",
            len(suspected_causes),
            len(uncertainties),
        )

        return CorrelationResult(
            suspected_causes=suspected_causes,
            evidence_timeline=timeline,
            confidence_factors=confidence_factors,
            unresolved_uncertainties=uncertainties,
        )

    def _build_timeline(self, evidence_list: list[Evidence]) -> list[tuple[datetime, str, str]]:
        """Build chronological timeline of evidence."""
        timeline = [
            (
                ev.collected_at,
                ev.evidence_id,
                f"{ev.kind.value}: {ev.summary[:100] if ev.summary else 'N/A'}",
            )
            for ev in evidence_list
        ]
        timeline.sort(key=lambda x: x[0])
        return timeline

    def _group_evidence_by_kind(
        self, evidence_list: list[Evidence]
    ) -> dict[EvidenceKind, list[Evidence]]:
        """Group evidence by kind."""
        grouped: dict[EvidenceKind, list[Evidence]] = {}
        for evidence in evidence_list:
            if evidence.kind not in grouped:
                grouped[evidence.kind] = []
            grouped[evidence.kind].append(evidence)
        return grouped

    def _correlate_deployment(
        self,
        evidence_by_kind: dict[EvidenceKind, list[Evidence]],
        incident_start: datetime,
    ) -> SuspectedCause | None:
        """Correlate incident with recent deployments."""
        deployments = evidence_by_kind.get(EvidenceKind.DEPLOYMENT_EVENT, [])
        if not deployments:
            return None

        # Find deployments within correlation window before incident
        recent_deployments = [
            dep
            for dep in deployments
            if incident_start - dep.collected_at <= self.correlation_window
            and dep.collected_at <= incident_start
        ]

        if not recent_deployments:
            return None

        # Most recent deployment is most suspicious
        latest_deployment = max(recent_deployments, key=lambda d: d.collected_at)
        time_since_deploy = incident_start - latest_deployment.collected_at

        # Higher confidence if incident started very soon after deployment
        confidence = max(
            0.3, 0.9 - (time_since_deploy.total_seconds() / self.correlation_window.total_seconds())
        )

        return SuspectedCause(
            cause_id=f"cause-deployment-{latest_deployment.evidence_id}",
            category=CauseCategory.DEPLOYMENT,
            description=f"Recent deployment detected {time_since_deploy.total_seconds():.0f}s before incident",
            confidence=confidence,
            evidence_ids=[latest_deployment.evidence_id],
            evidence_summary={
                "deployment_time": latest_deployment.collected_at.isoformat(),
                "time_since_deploy_seconds": time_since_deploy.total_seconds(),
                "deployment_summary": latest_deployment.summary,
            },
            first_seen=latest_deployment.collected_at,
            correlation_score=confidence,
        )

    def _correlate_pod_restarts(
        self,
        evidence_by_kind: dict[EvidenceKind, list[Evidence]],
        incident_start: datetime,
    ) -> SuspectedCause | None:
        """Correlate incident with pod restarts."""
        k8s_evidence = evidence_by_kind.get(EvidenceKind.KUBERNETES_OBJECT, [])
        if not k8s_evidence:
            return None

        # Look for restart patterns in data
        restart_evidence = [
            ev
            for ev in k8s_evidence
            if ev.payload
            and ("restart" in str(ev.payload).lower() or "crashloop" in str(ev.payload).lower())
        ]

        if not restart_evidence:
            return None

        recent_restarts = [
            ev
            for ev in restart_evidence
            if abs((ev.collected_at - incident_start).total_seconds())
            <= self.correlation_window.total_seconds()
        ]

        if not recent_restarts:
            return None

        confidence = min(0.85, 0.5 + (len(recent_restarts) * 0.15))

        return SuspectedCause(
            cause_id=f"cause-pod-restart-{recent_restarts[0].evidence_id}",
            category=CauseCategory.INFRASTRUCTURE,
            description=f"Pod restarts detected: {len(recent_restarts)} restart event(s)",
            confidence=confidence,
            evidence_ids=[ev.evidence_id for ev in recent_restarts],
            evidence_summary={
                "restart_count": len(recent_restarts),
                "first_restart": recent_restarts[0].collected_at.isoformat(),
            },
            first_seen=recent_restarts[0].collected_at,
            correlation_score=confidence,
        )

    def _correlate_database_errors(
        self,
        evidence_by_kind: dict[EvidenceKind, list[Evidence]],
        incident_start: datetime,
    ) -> SuspectedCause | None:
        """Correlate incident with database errors."""
        logs = evidence_by_kind.get(EvidenceKind.LOG_EXCERPT, [])
        if not logs:
            return None

        # Look for database-related errors
        db_errors = [
            log
            for log in logs
            if log.payload
            and any(
                keyword in str(log.payload).lower()
                for keyword in [
                    "database",
                    "postgres",
                    "pg",
                    "connection pool",
                    "timeout",
                    "deadlock",
                ]
            )
        ]

        if not db_errors:
            return None

        recent_db_errors = [
            ev
            for ev in db_errors
            if abs((ev.collected_at - incident_start).total_seconds())
            <= self.correlation_window.total_seconds()
        ]

        if not recent_db_errors:
            return None

        confidence = min(0.8, 0.4 + (len(recent_db_errors) * 0.1))

        return SuspectedCause(
            cause_id=f"cause-database-{recent_db_errors[0].evidence_id}",
            category=CauseCategory.DATABASE,
            description=f"Database errors detected: {len(recent_db_errors)} error(s)",
            confidence=confidence,
            evidence_ids=[ev.evidence_id for ev in recent_db_errors[:5]],
            evidence_summary={
                "error_count": len(recent_db_errors),
                "sample_error": recent_db_errors[0].summary,
            },
            first_seen=recent_db_errors[0].collected_at,
            correlation_score=confidence,
        )

    def _correlate_redis_errors(
        self,
        evidence_by_kind: dict[EvidenceKind, list[Evidence]],
        incident_start: datetime,
    ) -> SuspectedCause | None:
        """Correlate incident with Redis errors."""
        logs = evidence_by_kind.get(EvidenceKind.LOG_EXCERPT, [])
        if not logs:
            return None

        # Look for Redis-related errors
        redis_errors = [
            log
            for log in logs
            if log.payload
            and any(
                keyword in str(log.payload).lower()
                for keyword in ["redis", "cache", "connection refused", "timeout"]
            )
        ]

        if not redis_errors:
            return None

        recent_redis_errors = [
            ev
            for ev in redis_errors
            if abs((ev.collected_at - incident_start).total_seconds())
            <= self.correlation_window.total_seconds()
        ]

        if not recent_redis_errors:
            return None

        confidence = min(0.75, 0.4 + (len(recent_redis_errors) * 0.1))

        return SuspectedCause(
            cause_id=f"cause-redis-{recent_redis_errors[0].evidence_id}",
            category=CauseCategory.CACHE,
            description=f"Redis/cache errors detected: {len(recent_redis_errors)} error(s)",
            confidence=confidence,
            evidence_ids=[ev.evidence_id for ev in recent_redis_errors[:5]],
            evidence_summary={
                "error_count": len(recent_redis_errors),
                "sample_error": recent_redis_errors[0].summary,
            },
            first_seen=recent_redis_errors[0].collected_at,
            correlation_score=confidence,
        )

    def _correlate_application_errors(
        self,
        evidence_by_kind: dict[EvidenceKind, list[Evidence]],
        incident_start: datetime,
    ) -> SuspectedCause | None:
        """Correlate incident with application errors."""
        logs = evidence_by_kind.get(EvidenceKind.LOG_EXCERPT, [])
        if not logs:
            return None

        # Look for application exceptions/errors
        app_errors = [
            log
            for log in logs
            if log.payload
            and any(
                keyword in str(log.payload).lower()
                for keyword in ["exception", "error", "traceback", "failed", "panic"]
            )
        ]

        if not app_errors:
            return None

        recent_app_errors = [
            ev
            for ev in app_errors
            if abs((ev.collected_at - incident_start).total_seconds())
            <= self.correlation_window.total_seconds()
        ]

        if not recent_app_errors:
            return None

        confidence = min(0.7, 0.35 + (len(recent_app_errors) * 0.05))

        return SuspectedCause(
            cause_id=f"cause-app-error-{recent_app_errors[0].evidence_id}",
            category=CauseCategory.APPLICATION_ERROR,
            description=f"Application errors detected: {len(recent_app_errors)} error(s)",
            confidence=confidence,
            evidence_ids=[ev.evidence_id for ev in recent_app_errors[:10]],
            evidence_summary={
                "error_count": len(recent_app_errors),
                "sample_error": recent_app_errors[0].summary,
            },
            first_seen=recent_app_errors[0].collected_at,
            correlation_score=confidence,
        )

    def _correlate_resource_exhaustion(
        self,
        evidence_by_kind: dict[EvidenceKind, list[Evidence]],
        incident_start: datetime,
    ) -> SuspectedCause | None:
        """Correlate incident with resource exhaustion."""
        metrics = evidence_by_kind.get(EvidenceKind.METRIC_SERIES, [])
        k8s_evidence = evidence_by_kind.get(EvidenceKind.KUBERNETES_OBJECT, [])

        all_resource_evidence = metrics + k8s_evidence

        if not all_resource_evidence:
            return None

        # Look for OOM, high CPU, high memory patterns
        resource_issues = [
            ev
            for ev in all_resource_evidence
            if ev.payload
            and any(
                keyword in str(ev.payload).lower()
                for keyword in ["oom", "memory", "cpu", "disk", "throttle", "limit"]
            )
        ]

        if not resource_issues:
            return None

        recent_resource_issues = [
            ev
            for ev in resource_issues
            if abs((ev.collected_at - incident_start).total_seconds())
            <= self.correlation_window.total_seconds()
        ]

        if not recent_resource_issues:
            return None

        confidence = min(0.8, 0.4 + (len(recent_resource_issues) * 0.1))

        return SuspectedCause(
            cause_id=f"cause-resource-{recent_resource_issues[0].evidence_id}",
            category=CauseCategory.RESOURCE_EXHAUSTION,
            description=f"Resource exhaustion detected: {len(recent_resource_issues)} indicator(s)",
            confidence=confidence,
            evidence_ids=[ev.evidence_id for ev in recent_resource_issues[:5]],
            evidence_summary={
                "issue_count": len(recent_resource_issues),
                "sample_issue": recent_resource_issues[0].summary,
            },
            first_seen=recent_resource_issues[0].collected_at,
            correlation_score=confidence,
        )

    def _calculate_confidence_factors(
        self, suspected_causes: list[SuspectedCause], evidence_list: list[Evidence]
    ) -> dict[str, float]:
        """Calculate factors that contribute to overall confidence."""
        factors = {
            "evidence_count": min(1.0, len(evidence_list) / 10),
            "evidence_diversity": len({ev.kind for ev in evidence_list}) / len(EvidenceKind),
            "cause_agreement": len(suspected_causes) / 5 if suspected_causes else 0.0,
        }

        # Normalize to 0-1 range
        for key in factors:
            factors[key] = min(1.0, max(0.0, factors[key]))

        return factors
