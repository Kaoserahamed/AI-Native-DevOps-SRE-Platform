"""Agent identity, execution and decision contract.

This is the schema behind the audit requirement "who/what agent, input evidence, decision, confidence,
action, result". It also encodes the two safety rules the evaluation suite depends on:

* a diagnosis that is not ``insufficient_evidence`` must cite evidence that was actually provided, and
* ``insufficient_evidence`` is a first-class outcome with low confidence and no recommended action.

:class:`AgentInvocation` is the per-run envelope: it records the *identity* of the agent that ran (type,
version, prompt version, model/provider), the evidence it was given, the decision it produced, the policy
result that gated its action, the action itself and the outcome. An invocation with an action but no policy
verdict — or with an executed action that needed approval but records none — is rejected, so the record of a
production change can never be incomplete.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Final, Self

from pydantic import Field, StringConstraints, computed_field, model_validator

from packages.contracts.common import (
    Confidence,
    Counter,
    Digest,
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
MAX_EVIDENCE_IDS: Final[int] = 64
MAX_POLICY_VIOLATIONS: Final[int] = 16

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
    INFRASTRUCTURE_EVENT = "infrastructure_event"
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
        default_factory=list,
        description="Identifiers of the evidence that was provided to the agent.",
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


class AgentIdentity(ValueModel):
    """Who ran, under which instructions and on which model.

    The identity is the first half of the audit answer: an invocation is only meaningful if the exact
    prompt version and model that produced it are recorded alongside the result.
    """

    agent_type: AgentType
    agent_version: VersionRef
    prompt_version: VersionRef
    provider: MachineName
    model: ShortText

    @computed_field(  # type: ignore[prop-decorator]
        description="Audit actor id for this identity, for example incident_agent@0.1.0."
    )
    @property
    def actor_id(self) -> str:
        """Return the ``<agent_type>@<version>`` principal recorded on every audit event."""
        return f"{self.agent_type.value}@{self.agent_version}"

    @computed_field(  # type: ignore[prop-decorator]
        description="Provider and model reference, for example openai_compatible/gpt-5-mini."
    )
    @property
    def model_ref(self) -> str:
        """Return the ``provider/model`` reference the operator dashboard reports on."""
        return f"{self.provider}/{self.model}"


class PolicyOutcome(StrEnum):
    """Result of the policy evaluation that gated an agent action."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"
    NOT_EVALUATED = "not_evaluated"


class PolicyVerdict(ValueModel):
    """The recorded policy result attached to an agent invocation.

    ``not_evaluated`` is explicit rather than absent: a read-only agent still records that no policy
    decision was required, which is what makes "no action happened without a policy check" auditable.
    """

    outcome: PolicyOutcome = PolicyOutcome.NOT_EVALUATED
    evaluated_at: UtcDatetime | None = None
    required_approvals: Counter = 0
    violations: list[ShortText] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        """Reject a verdict that does not describe an actual evaluation."""
        if len(self.violations) > MAX_POLICY_VIOLATIONS:
            raise ValueError(f"at most {MAX_POLICY_VIOLATIONS} policy violations are recorded")
        if self.outcome is PolicyOutcome.NOT_EVALUATED:
            if self.evaluated_at is not None:
                raise ValueError("not_evaluated must not record an evaluation time")
            if self.required_approvals:
                raise ValueError("not_evaluated must not require approvals")
            if self.violations:
                raise ValueError("not_evaluated must not record violations")
            return self
        if self.evaluated_at is None:
            raise ValueError(f"{self.outcome} requires the time it was evaluated")
        if self.outcome is PolicyOutcome.DENY and not self.violations:
            raise ValueError("a deny verdict must name at least one violation")
        return self


class InvocationOutcome(StrEnum):
    """How one agent invocation ended."""

    NO_ACTION = "no_action"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    DIAGNOSIS_PRODUCED = "diagnosis_produced"
    AWAITING_APPROVAL = "awaiting_approval"
    ACTION_SUCCEEDED = "action_succeeded"
    ACTION_FAILED = "action_failed"
    DENIED_BY_POLICY = "denied_by_policy"
    AGENT_FAILED = "agent_failed"


class AgentAction(ValueModel):
    """The action an invocation proposed, was denied, or executed."""

    category: RemediationCategory
    action_hash: Digest = Field(
        description="Canonical digest of the action; approvals and idempotency keys bind to this value."
    )
    proposal_id: Identifier | None = None
    approval_id: Identifier | None = Field(
        default=None, description="Approval that authorised an executed production change."
    )
    tool: MachineName | None = Field(default=None, description="Tool that performed the action.")


#: Outcomes that must carry an action, and the policy verdict each of them implies.
ACTION_OUTCOMES: Final[Mapping[InvocationOutcome, PolicyOutcome]] = {
    InvocationOutcome.AWAITING_APPROVAL: PolicyOutcome.REQUIRE_APPROVAL,
    InvocationOutcome.ACTION_SUCCEEDED: PolicyOutcome.ALLOW,
    InvocationOutcome.ACTION_FAILED: PolicyOutcome.ALLOW,
    InvocationOutcome.DENIED_BY_POLICY: PolicyOutcome.DENY,
}


class AgentInvocation(PlatformModel):
    """One recorded agent invocation: identity, inputs, decision, policy result, action and outcome."""

    invocation_id: Identifier
    run_id: Identifier
    incident_id: Identifier
    identity: AgentIdentity
    started_at: UtcDatetime
    completed_at: UtcDatetime
    evidence_ids: list[Identifier] = Field(
        default_factory=list,
        max_length=MAX_EVIDENCE_IDS,
        description="Identifiers of the evidence that was provided to the agent.",
    )
    decision_id: Identifier | None = None
    diagnosis: DiagnosisCategory | None = None
    confidence: Confidence | None = None
    policy_result: PolicyVerdict = Field(default_factory=PolicyVerdict)
    action: AgentAction | None = None
    outcome: InvocationOutcome
    correlation_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        """Enforce that the recorded outcome, policy verdict and action agree with each other."""
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not be earlier than started_at")
        if (self.diagnosis is None) != (self.confidence is None):
            raise ValueError("diagnosis and confidence are recorded together, or not at all")
        if self.decision_id is not None and self.diagnosis is None:
            raise ValueError("a decision id without a diagnosis cannot be audited")

        if self.outcome is InvocationOutcome.INSUFFICIENT_EVIDENCE and (
            self.confidence is not None and self.confidence > 0.5
        ):
            raise ValueError("insufficient_evidence must not claim high confidence")

        expected_policy = ACTION_OUTCOMES.get(self.outcome)
        if self.action is None:
            if expected_policy is not None:
                raise ValueError(f"{self.outcome} must record the action it applies to")
            if self.policy_result.outcome is not PolicyOutcome.NOT_EVALUATED:
                raise ValueError(
                    "a policy verdict without an action has nothing to describe; "
                    "record the action or leave the verdict not_evaluated"
                )
            return self

        if self.policy_result.outcome is not expected_policy:
            raise ValueError(
                f"{self.outcome} requires a {expected_policy} policy result, "
                f"got {self.policy_result.outcome}"
            )
        if self.policy_result.required_approvals > 0 and self.action.approval_id is None:
            raise ValueError(
                "an action that required approval must record the approval that authorised it"
            )
        return self
