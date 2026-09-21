"""Core incident analysis logic using LLM for diagnosis."""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from packages.contracts.common import Confidence, Identifier, Severity
from packages.contracts.incidents import CauseCategory, Incident, IncidentStatus, SuspectedCause
from packages.llm.provider import LlmProvider
from packages.llm.types import ChatMessage, LlmRequest, ModelConfig, Role

logger = logging.getLogger(__name__)


class AnalysisResult(BaseModel):
    """Structured LLM output for incident analysis."""

    category: CauseCategory
    description: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1, max_length=1000)
    insufficient_evidence: bool = False


class IncidentAnalyzer:
    """Analyzes incidents using LLM and evidence retrieval."""

    def __init__(
        self,
        llm_provider: LlmProvider,
        system_prompt: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize the incident analyzer.

        Parameters
        ----------
        llm_provider
            LLM provider for diagnosis
        system_prompt
            Optional system prompt override for testing
        timeout_seconds
            Timeout for LLM calls
        """
        self.llm = llm_provider
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.timeout_seconds = timeout_seconds

    def _default_system_prompt(self) -> str:
        """Return the default system prompt for incident analysis."""
        return """You are an expert SRE assistant analyzing production incidents.

Your task is to:
1. Review the incident alert and evidence
2. Correlate signals across logs, metrics, and traces
3. Identify the most likely root cause
4. Express confidence based on evidence quality
5. Indicate when evidence is insufficient

Respond with structured output containing:
- category: one of deployment_regression, dependency_failure, resource_exhaustion,
  configuration_error, traffic_anomaly, code_defect, infrastructure_event, unknown
- description: concise summary of the suspected cause
- confidence: 0.0 to 1.0 based on evidence strength
- reasoning: brief explanation citing specific evidence
- insufficient_evidence: true if you cannot make a confident assessment

Always cite specific evidence. If evidence is ambiguous or missing, set insufficient_evidence=true."""

    async def analyze(
        self,
        incident_id: Identifier,
        alert_description: str,
        evidence: dict[str, Any],
        severity: Severity,
    ) -> tuple[SuspectedCause | None, float]:
        """Analyze an incident and return a suspected cause.

        Parameters
        ----------
        incident_id
            Unique identifier for the incident
        alert_description
            Description from the triggering alert
        evidence
            Dictionary of evidence items (logs, metrics, traces)
        severity
            Incident severity level

        Returns
        -------
        tuple[SuspectedCause | None, float]
            Suspected cause if analysis succeeded, and confidence score
        """
        evidence_summary = self._format_evidence(evidence)

        messages = [
            ChatMessage(role=Role.SYSTEM, content=self.system_prompt),
            ChatMessage(
                role=Role.USER,
                content=f"""Analyze this incident:

Incident ID: {incident_id}
Severity: {severity}
Alert: {alert_description}

Evidence:
{evidence_summary}

Provide your analysis.""",
            ),
        ]

        try:
            # Use the first supported model
            model = self.llm.supported_models[0]
            model_config = ModelConfig(
                provider=self.llm.name,
                model=model,
                max_tokens=1000,
                temperature=0.1,
                timeout_seconds=self.timeout_seconds,
            )

            request = LlmRequest(
                model_config=model_config,
                messages=messages,
            )

            deadline = time.monotonic() + self.timeout_seconds
            result = self.llm.complete_structured(request, AnalysisResult, deadline=deadline)

            if result.insufficient_evidence:
                logger.warning(
                    "Insufficient evidence for incident %s: %s",
                    incident_id,
                    result.reasoning,
                )
                return None, 0.0

            suspected_cause = SuspectedCause(
                category=result.category,
                description=result.description,
                confidence=Confidence(result.confidence),
                evidence_ids=list(evidence.keys()),
            )

            logger.info(
                "Analysis complete for incident %s: %s (confidence: %.2f)",
                incident_id,
                result.category,
                result.confidence,
            )

            return suspected_cause, result.confidence

        except Exception as e:
            logger.exception("Analysis failed for incident %s: %s", incident_id, e)
            return None, 0.0

    def _format_evidence(self, evidence: dict[str, Any]) -> str:
        """Format evidence dictionary for LLM prompt."""
        lines = []
        for evidence_id, data in evidence.items():
            lines.append(f"\n{evidence_id}:")
            if isinstance(data, dict):
                for key, value in data.items():
                    lines.append(f"  {key}: {value}")
            else:
                lines.append(f"  {data}")
        return "\n".join(lines) if lines else "No evidence available"


async def analyze_incident(
    incident: Incident,
    evidence: dict[str, Any],
    llm_provider: LlmProvider,
) -> Incident:
    """Analyze an incident and update it with suspected causes.

    Parameters
    ----------
    incident
        Incident to analyze
    evidence
        Evidence dictionary
    llm_provider
        LLM provider for analysis

    Returns
    -------
    Incident
        Updated incident with analysis results
    """
    analyzer = IncidentAnalyzer(llm_provider)

    alert_description = f"Alert triggered for {incident.service}: {incident.title}"

    suspected_cause, confidence = await analyzer.analyze(
        incident.incident_id,
        alert_description,
        evidence,
        incident.severity,
    )

    if suspected_cause is not None:
        # Create updated incident with new data
        updated_incident = incident.model_copy(
            update={
                "suspected_causes": [suspected_cause],
                "confidence": Confidence(confidence),
                "status": IncidentStatus.INVESTIGATING,
            }
        )
        return updated_incident

    return incident
