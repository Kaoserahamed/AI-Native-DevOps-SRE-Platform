"""Core incident analysis logic using LLM for diagnosis.

Two Phase 12 rules are enforced here rather than left to convention:

* **Prompt security (Task 12.2).** The alert description and every piece of telemetry are attacker-
  influenceable, so they never share a message with the instructions: :func:`build_evidence_prompt` fences
  them in the user message, neutralizes instruction-like content and bounds the payload.
* **Agent identity (Task 12.1).** When a recorder is supplied, the run records the agent identity (type,
  version, prompt version, provider, model), the evidence identifiers, the decision and its confidence, and
  the outcome. A failed run is recorded as ``agent_failed`` instead of disappearing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import logging
import time
from typing import Any, Final

from pydantic import BaseModel, Field

from packages.contracts.agents import (
    AgentInvocation,
    AgentType,
    DiagnosisCategory,
    InvocationOutcome,
)
from packages.contracts.common import Confidence, Identifier, Severity
from packages.contracts.incidents import CauseCategory, Incident, IncidentStatus, SuspectedCause
from packages.governance.identity import AgentInvocationRecorder, AgentInvocationRun
from packages.governance.prompts import EvidenceItem, PromptBuild, build_evidence_prompt
from packages.llm.provider import LlmProvider
from packages.llm.types import LlmRequest, ModelConfig

logger = logging.getLogger(__name__)


class AnalysisResult(BaseModel):
    """Structured LLM output for incident analysis."""

    category: CauseCategory
    description: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1, max_length=1000)
    insufficient_evidence: bool = False


#: The analyzer's output vocabulary mapped onto the versioned diagnosis vocabulary.
DIAGNOSIS_BY_CAUSE: Final[Mapping[CauseCategory, DiagnosisCategory]] = {
    CauseCategory.DEPLOYMENT_REGRESSION: DiagnosisCategory.DEPLOYMENT_REGRESSION,
    CauseCategory.DEPENDENCY_FAILURE: DiagnosisCategory.DEPENDENCY_FAILURE,
    CauseCategory.RESOURCE_EXHAUSTION: DiagnosisCategory.RESOURCE_EXHAUSTION,
    CauseCategory.CONFIGURATION_ERROR: DiagnosisCategory.CONFIGURATION_ERROR,
    CauseCategory.TRAFFIC_ANOMALY: DiagnosisCategory.TRAFFIC_ANOMALY,
    CauseCategory.CODE_DEFECT: DiagnosisCategory.CODE_DEFECT,
    CauseCategory.INFRASTRUCTURE_EVENT: DiagnosisCategory.INFRASTRUCTURE_EVENT,
    CauseCategory.UNKNOWN: DiagnosisCategory.INSUFFICIENT_EVIDENCE,
}

#: Highest confidence an ``insufficient_evidence`` result may claim.
MAX_INSUFFICIENT_CONFIDENCE: Final[float] = 0.5


class IncidentAnalyzer:
    """Analyzes incidents using LLM and evidence retrieval."""

    def __init__(
        self,
        llm_provider: LlmProvider,
        system_prompt: str | None = None,
        timeout_seconds: float = 30.0,
        recorder: AgentInvocationRecorder | None = None,
    ) -> None:
        """Initialize the incident analyzer.

        Parameters
        ----------
        llm_provider
            LLM provider for diagnosis
        system_prompt
            Optional system prompt override for testing. An override changes agent behaviour, so a deployment
            that uses one must declare a matching ``prompt_version`` through its own
            :class:`~packages.governance.identity.AgentRegistry`.
        timeout_seconds
            Timeout for LLM calls
        recorder
            Optional invocation recorder. When supplied, every analysis is recorded with its identity,
            evidence identifiers, decision, confidence and outcome.
        """
        self.llm = llm_provider
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.timeout_seconds = timeout_seconds
        self.recorder = recorder

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
        run_id: Identifier | None = None,
        correlation_id: Identifier | None = None,
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
        run_id
            Control-loop run identifier recorded on the invocation; derived from the incident when omitted.
        correlation_id
            Correlation id shared with the rest of the control loop.

        Returns
        -------
        tuple[SuspectedCause | None, float]
            Suspected cause if analysis succeeded, and confidence score
        """
        build = self._build_prompt(
            incident_id=incident_id,
            alert_description=alert_description,
            evidence=evidence,
            severity=severity,
        )
        run = self._begin_run(
            incident_id=incident_id,
            evidence_ids=build.evidence_ids,
            run_id=run_id,
            correlation_id=correlation_id,
        )

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
                messages=build.messages,
            )

            deadline = time.monotonic() + self.timeout_seconds
            result = self.llm.complete_structured(request, AnalysisResult, deadline=deadline)

            if result.insufficient_evidence:
                logger.warning(
                    "Insufficient evidence for incident %s: %s",
                    incident_id,
                    result.reasoning,
                )
                self._finish(
                    run,
                    diagnosis=DiagnosisCategory.INSUFFICIENT_EVIDENCE,
                    confidence=Confidence(min(result.confidence, MAX_INSUFFICIENT_CONFIDENCE)),
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

            self._finish(
                run,
                diagnosis=DIAGNOSIS_BY_CAUSE[result.category],
                confidence=Confidence(result.confidence),
            )
            return suspected_cause, result.confidence

        except Exception as e:
            logger.exception("Analysis failed for incident %s: %s", incident_id, e)
            self._finish(run, outcome=InvocationOutcome.AGENT_FAILED)
            return None, 0.0

    def _build_prompt(
        self,
        *,
        incident_id: Identifier,
        alert_description: str,
        evidence: Mapping[str, Any],
        severity: Severity,
    ) -> PromptBuild:
        """Return the messages for one analysis call with instructions and untrusted text kept apart."""
        build = build_evidence_prompt(
            instructions=self.system_prompt,
            context=(
                f"Incident id: {incident_id}\n"
                f"Severity: {severity.value}\n"
                f"Triggering alert: {alert_description}"
            ),
            evidence=[
                EvidenceItem(evidence_id=evidence_id, text=self._render_item(data))
                for evidence_id, data in evidence.items()
            ],
        )
        if build.tampered:
            logger.warning(
                "Evidence for incident %s contained instruction-like content (%s); it was neutralized",
                incident_id,
                build.summary(),
            )
        return build

    def _begin_run(
        self,
        *,
        incident_id: Identifier,
        evidence_ids: Sequence[str],
        run_id: Identifier | None,
        correlation_id: Identifier | None,
    ) -> AgentInvocationRun | None:
        """Open an invocation record, or return ``None`` when no recorder is configured."""
        if self.recorder is None:
            return None
        return self.recorder.begin(
            agent_type=AgentType.INCIDENT_AGENT,
            run_id=run_id or f"RUN-{incident_id}",
            incident_id=incident_id,
            provider=self.llm.name,
            model=self.llm.supported_models[0],
            evidence_ids=list(evidence_ids),
            correlation_id=correlation_id,
        )

    def _finish(
        self,
        run: AgentInvocationRun | None,
        *,
        diagnosis: DiagnosisCategory | None = None,
        confidence: Confidence | None = None,
        outcome: InvocationOutcome | None = None,
    ) -> AgentInvocation | None:
        """Close an invocation record, recording the decision when one was made."""
        if run is None:
            return None
        if diagnosis is not None and confidence is not None:
            run.record_decision(diagnosis, confidence)
        return run.finish(outcome)

    def _render_item(self, data: Any) -> str:
        """Render one evidence payload as bounded, line-oriented text."""
        if isinstance(data, Mapping):
            return "\n".join(f"{key}: {value}" for key, value in data.items())
        return str(data)


async def analyze_incident(
    incident: Incident,
    evidence: dict[str, Any],
    llm_provider: LlmProvider,
    recorder: AgentInvocationRecorder | None = None,
    correlation_id: Identifier | None = None,
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
    recorder
        Optional invocation recorder; when supplied, the analysis is recorded with its agent identity.
    correlation_id
        Correlation id shared with the rest of the control loop.

    Returns
    -------
    Incident
        Updated incident with analysis results
    """
    analyzer = IncidentAnalyzer(llm_provider, recorder=recorder)

    alert_description = f"Alert triggered for {incident.service}: {incident.title}"

    suspected_cause, confidence = await analyzer.analyze(
        incident.incident_id,
        alert_description,
        evidence,
        incident.severity,
        correlation_id=correlation_id,
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
