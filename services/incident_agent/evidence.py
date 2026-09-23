"""Evidence retrieval layer for incident analysis.

Retrieves bounded evidence from logs, metrics, traces, and Kubernetes, with time-window
constraints and size limits to prevent unbounded telemetry ingestion.

Every retrieval goes through the agent's authorized tool catalogue (Task 12.3): a retrieval adapter is a tool
call like any other, so it is allowlisted, argument-checked and audited, and an agent that lacks the required
permission simply receives no evidence instead of reaching the backend anyway.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from packages.contracts.agents import AgentType
from packages.contracts.common import Environment, Identifier
from packages.governance.authorization import ToolAuthorizer, ToolRequest
from packages.governance.identity import AGENT_VERSION
from packages.governance.tools import AgentTool

logger = logging.getLogger(__name__)


@dataclass
class EvidenceConstraints:
    """Time and size constraints for evidence retrieval."""

    time_window_minutes: int = 30
    max_log_entries: int = 100
    max_metric_points: int = 50
    max_trace_samples: int = 20


@dataclass
class Evidence:
    """A single piece of evidence with metadata."""

    evidence_id: Identifier
    source_type: str  # log, metric, trace, kubernetes, deployment
    timestamp: datetime
    data: dict[str, Any]
    description: str


class EvidenceRetriever:
    """Retrieves bounded evidence for incident analysis."""

    def __init__(
        self,
        constraints: EvidenceConstraints | None = None,
        authorizer: ToolAuthorizer | None = None,
        agent_type: AgentType = AgentType.INCIDENT_AGENT,
        agent_version: str = AGENT_VERSION,
        environment: Environment = Environment.PRODUCTION,
    ) -> None:
        """Initialize evidence retriever.

        Parameters
        ----------
        constraints
            Optional constraints override for testing
        authorizer
            Tool authorizer that gates every retrieval. The default authorizer allows only the read-only tools
            the incident agent is permitted to use, and audits nothing unless a trail is attached.
        agent_type
            Agent the retrieval runs as; determines the permission set that applies.
        agent_version
            Version recorded in the tool audit events.
        environment
            Environment the incident lives in. It defaults to ``production`` so an unconfigured retriever is
            the strictest one.
        """
        self.constraints = constraints or EvidenceConstraints()
        self.authorizer = authorizer or ToolAuthorizer()
        self.agent_type = agent_type
        self.agent_version = agent_version
        self.environment = environment

    def _authorize(
        self, tool: AgentTool, arguments: dict[str, object], incident_id: Identifier
    ) -> bool:
        """Return whether the agent may use ``tool`` for this retrieval, auditing the decision."""
        request = ToolRequest(
            agent_type=self.agent_type,
            agent_version=self.agent_version,
            tool=tool,
            arguments=arguments,
            environment=self.environment,
            incident_id=incident_id,
        )
        result = self.authorizer.authorize(request)
        if not result.allowed:
            logger.warning(
                "Evidence retrieval refused for agent %s: tool %s (%s)",
                self.agent_type.value,
                tool.value,
                result.explain(),
            )
        return result.allowed

    async def retrieve_evidence(
        self,
        incident_id: Identifier,
        service: str,
        detected_at: datetime,
    ) -> dict[str, Any]:
        """Retrieve bounded evidence for an incident.

        Parameters
        ----------
        incident_id
            Incident identifier for correlation
        service
            Service name to query
        detected_at
            When the incident was detected

        Returns
        -------
        dict[str, Any]
            Dictionary of evidence items keyed by evidence ID
        """
        evidence_dict: dict[str, Any] = {}

        # Define time window
        end_time = detected_at
        start_time = end_time - timedelta(minutes=self.constraints.time_window_minutes)

        logger.info(
            "Retrieving evidence for incident %s, service %s, window [%s, %s]",
            incident_id,
            service,
            start_time.isoformat(),
            end_time.isoformat(),
        )

        # Retrieve from each source, each through the authorized tool catalogue
        log_evidence = await self._retrieve_logs(incident_id, service, start_time, end_time)
        metric_evidence = await self._retrieve_metrics(incident_id, service, start_time, end_time)
        trace_evidence = await self._retrieve_traces(incident_id, service, start_time, end_time)
        k8s_evidence = await self._retrieve_kubernetes_events(
            incident_id, service, start_time, end_time
        )
        deployment_evidence = await self._retrieve_deployment_history(
            incident_id, service, start_time, end_time
        )

        # Combine all evidence
        all_evidence = (
            log_evidence + metric_evidence + trace_evidence + k8s_evidence + deployment_evidence
        )

        # Convert to dictionary
        for ev in all_evidence:
            evidence_dict[ev.evidence_id] = {
                "source_type": ev.source_type,
                "timestamp": ev.timestamp.isoformat(),
                "description": ev.description,
                **ev.data,
            }

        logger.info("Retrieved %d evidence items for incident %s", len(evidence_dict), incident_id)

        return evidence_dict

    async def _retrieve_logs(
        self, incident_id: Identifier, service: str, start_time: datetime, end_time: datetime
    ) -> list[Evidence]:
        """Retrieve log evidence within constraints."""
        if not self._authorize(
            AgentTool.LOG_QUERY,
            {
                "service": service,
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "limit": self.constraints.max_log_entries,
            },
            incident_id=incident_id,
        ):
            return []

        logger.debug(
            "Retrieving logs for %s from %s to %s (max %d entries)",
            service,
            start_time,
            end_time,
            self.constraints.max_log_entries,
        )

        # Return empty for now - adapter implementation would go here
        return []

    async def _retrieve_metrics(
        self, incident_id: Identifier, service: str, start_time: datetime, end_time: datetime
    ) -> list[Evidence]:
        """Retrieve metric evidence within constraints."""
        if not self._authorize(
            AgentTool.PROMETHEUS_QUERY,
            {
                "query": f'{{service="{service}"}}',
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "limit": self.constraints.max_metric_points,
            },
            incident_id=incident_id,
        ):
            return []

        logger.debug(
            "Retrieving metrics for %s from %s to %s (max %d points)",
            service,
            start_time,
            end_time,
            self.constraints.max_metric_points,
        )

        # Stub - would query Prometheus or similar
        return []

    async def _retrieve_traces(
        self, incident_id: Identifier, service: str, start_time: datetime, end_time: datetime
    ) -> list[Evidence]:
        """Retrieve trace evidence within constraints."""
        if not self._authorize(
            AgentTool.TRACE_QUERY,
            {
                "service": service,
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "limit": self.constraints.max_trace_samples,
            },
            incident_id=incident_id,
        ):
            return []

        logger.debug(
            "Retrieving traces for %s from %s to %s (max %d samples)",
            service,
            start_time,
            end_time,
            self.constraints.max_trace_samples,
        )

        # Stub - would query trace backend
        return []

    async def _retrieve_kubernetes_events(
        self, incident_id: Identifier, service: str, start_time: datetime, end_time: datetime
    ) -> list[Evidence]:
        """Retrieve Kubernetes event evidence."""
        if not self._authorize(
            AgentTool.KUBERNETES_INSPECT,
            {"workload": service, "namespace": "demo"},
            incident_id=incident_id,
        ):
            return []

        logger.debug(
            "Retrieving k8s events for %s from %s to %s",
            service,
            start_time,
            end_time,
        )

        # Stub - would use kubernetes_client package
        return []

    async def _retrieve_deployment_history(
        self, incident_id: Identifier, service: str, start_time: datetime, end_time: datetime
    ) -> list[Evidence]:
        """Retrieve deployment history from GitHub or deployment system."""
        if not self._authorize(
            AgentTool.DEPLOYMENT_HISTORY,
            {"service": service, "limit": 10},
            incident_id=incident_id,
        ):
            return []

        logger.debug(
            "Retrieving deployment history for %s from %s to %s",
            service,
            start_time,
            end_time,
        )

        # Stub - would use github_client package
        return []


async def retrieve_incident_evidence(
    incident_id: Identifier,
    service: str,
    detected_at: datetime,
    constraints: EvidenceConstraints | None = None,
) -> dict[str, Any]:
    """Convenience function to retrieve evidence for an incident.

    Parameters
    ----------
    incident_id
        Incident identifier
    service
        Service name
    detected_at
        Detection timestamp
    constraints
        Optional retrieval constraints

    Returns
    -------
    dict[str, Any]
        Evidence dictionary
    """
    retriever = EvidenceRetriever(constraints)
    return await retriever.retrieve_evidence(incident_id, service, detected_at)
