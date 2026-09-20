"""Agent identity, execution and decision contract.

This is the schema behind the audit requirement "who/what agent, input evidence, decision, confidence,
action, result". It also encodes the two safety rules the evaluation suite depends on:

* a diagnosis that is not ``insufficient_evidence`` must cite evidence that was actually provided, and
* ``insufficient_evidence`` is a first-class outcome with low confidence and no recommended action.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from packages.contracts.common import (
    Confidence,
    Counter,
    Identifier,
    LongText,
    MachineName,
    PlatformModel,
    ShortText,
    UtcDatetime,
    ValueModel,
    VersionRef,
)
from packages.contracts.remediation import RemediationCategory

MAX_CITATION_LENGTH = 500

CitationQuote = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_CITATION_LENGTH)
]
CostUsd = Annotated[float, Field(ge=0.0)]


class AgentType(StrEnum):
    """The agents that can run inside the worker."""

    ANOMALY_AGENT = "anomaly_agent"
    INCIDENT_AGENT = "incident_agent"
    REMEDIATION_AGENT = "remediation_agent"
    COST_AGENT = "cost_agent"


class DiagnosisCategory(StrEnum):
    """Diagnosis outcomes, including the honest "we do not know" outcome."""

    DEPLOYMENT_REGRESSION = "deployment_regression"
    DEPENDENCY_FAILURE = "dependency_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CONFIGURATION_ERROR = "configuration_error"
    TRAFFIC_ANOMALY = "traffic_anomaly"
    CODE_DEFECT = "code_defect"
    TELEMETRY_GAP = "telemetry_gap"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_ACTION_REQUIRED = "no_action_required"


class Citation(ValueModel):
    """A verbatim quote from one evidence item, used to ground the diagnosis."""

    evidence_id: Identifier
    quote: CitationQuote
    note: ShortText | None = None


class AgentUsage(ValueModel):
    """Token, cost, latency and tool accounting for one agent run."""

    prompt_tokens: Counter = 0
    completion_tokens: Counter = 0
    cost_usd: CostUsd = 0.0
    latency_ms: Counter = 0
    model_calls: Counter = 0
    tool_calls: Counter = 0
    iterations: Counter = 0
    evidence_bytes: Counter = 0


class AgentDecision(PlatformModel):
    """One recorded agent decision with full provenance."""

    decision_id: Identifier
    run_id: Identifier
    incident_id: Identifier
    agent_type: AgentType
    agent_version: VersionRef
    prompt_version: VersionRef
    provider: MachineName
    model: ShortText
    created_at: UtcDatetime
    diagnosis: DiagnosisCategory
    summary: ShortText
    confidence: Confidence
    evidence_ids: list[Identifier] = Field(
        default_factory=list, description="Identifiers of the evidence that was provided to the agent."
    )
    citations: list[Citation] = Field(default_factory=list)
    uncertainty: LongText | None = None
    recommended_action: RemediationCategory | None = None
    usage: AgentUsage = Field(default_factory=AgentUsage)
    correlation_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_grounding(self) -> Self:
        """Enforce evidence grounding and the safe shape of an insufficient-evidence result."""
        if self.diagnosis is DiagnosisCategory.INSUFFICIENT_EVIDENCE:
            if self.confidence > 0.5:
                raise ValueError("insufficient_evidence must not claim high confidence")
            if self.recommended_action is not None:
                raise ValueError("insufficient_evidence must not recommend an action")
            return self

        if not self.evidence_ids:
            raise ValueError(f"{self.diagnosis} requires at least one evidence item")
        if not self.citations:
            raise ValueError(f"{self.diagnosis} requires at least one citation")

        provided = set(self.evidence_ids)
        for citation in self.citations:
            if citation.evidence_id not in provided:
                raise ValueError(
                    f"citation refers to evidence that was not provided: {citation.evidence_id}"
                )

        if (
            self.diagnosis is DiagnosisCategory.NO_ACTION_REQUIRED
            and self.recommended_action is not None
        ):
            raise ValueError("no_action_required must not recommend an action")
        if (
            self.diagnosis is not DiagnosisCategory.NO_ACTION_REQUIRED
            and self.recommended_action is None
        ):
            raise ValueError(f"{self.diagnosis} must recommend a remediation category")
        return self
