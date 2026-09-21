"""Agent identity registry and invocation recording.

Every agent invocation is recorded, and it is recorded completely. This module supplies the two halves of
that promise:

* :class:`AgentRegistry` declares, in one place, which code version and which prompt version each agent type
  runs under. An agent type that was never declared cannot open an invocation, so an unaudited agent cannot
  quietly appear in the control loop.
* :class:`AgentInvocationRecorder` records an invocation through :class:`AgentInvocationRun`: the identity is
  fixed when the run opens, the steps are ordered and write-once (decision, then policy, then action), and
  the finished record is appended to the audit trail when one is configured.

The provider and model are bound at :meth:`AgentInvocationRecorder.begin`, because the identity that matters
is the one that actually answered, not the one that was configured.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Self

from packages.contracts.agents import (
    AgentAction,
    AgentIdentity,
    AgentInvocation,
    AgentType,
    DiagnosisCategory,
    InvocationOutcome,
    PolicyOutcome,
    PolicyVerdict,
)
from packages.contracts.audit import AuditEvent
from packages.contracts.common import Confidence, Identifier, PrincipalId, VersionRef
from packages.governance.audit import AuditTrail
from packages.governance.prompts import (
    ANOMALY_DETECTION_PROMPT_VERSION,
    COST_RECOMMENDATION_PROMPT_VERSION,
    INCIDENT_ANALYSIS_PROMPT_VERSION,
    REMEDIATION_PROPOSAL_PROMPT_VERSION,
)
from packages.governance.support import (
    DECISION_ID_PREFIX,
    INVOCATION_ID_PREFIX,
    Clock,
    IdSource,
    new_identifier,
    utc_now,
)


@dataclass(frozen=True, slots=True)
class AgentVersioning:
    """The two versioned inputs that define an agent's behaviour."""

    agent_version: VersionRef
    prompt_version: VersionRef


AGENT_VERSION: Final[str] = "0.1.0"

#: Declared identity of every agent type the platform runs.
DEFAULT_VERSIONING: Final[Mapping[AgentType, AgentVersioning]] = {
    AgentType.ANOMALY_AGENT: AgentVersioning(AGENT_VERSION, ANOMALY_DETECTION_PROMPT_VERSION),
    AgentType.INCIDENT_AGENT: AgentVersioning(AGENT_VERSION, INCIDENT_ANALYSIS_PROMPT_VERSION),
    AgentType.REMEDIATION_AGENT: AgentVersioning(
        AGENT_VERSION, REMEDIATION_PROPOSAL_PROMPT_VERSION
    ),
    AgentType.COST_AGENT: AgentVersioning(AGENT_VERSION, COST_RECOMMENDATION_PROMPT_VERSION),
}


class AgentRegistry:
    """The declared identity of every agent: code version and prompt version per agent type."""

    def __init__(self, versioning: Mapping[AgentType, AgentVersioning] | None = None) -> None:
        """Create a registry, defaulting to the platform's declared agents.

        Parameters
        ----------
        versioning
            Declared versioning per agent type; the platform defaults are used when omitted.
        """
        self._versioning: dict[AgentType, AgentVersioning] = dict(versioning or DEFAULT_VERSIONING)

    def register(
        self, agent_type: AgentType, versioning: AgentVersioning, *, replace: bool = False
    ) -> None:
        """Declare an agent's identity.

        Raises
        ------
        ValueError
            When the agent type is already declared and ``replace`` is not set, because silently changing an
            agent's declared version would rewrite history.
        """
        if agent_type in self._versioning and not replace:
            raise ValueError(
                f"{agent_type.value} is already declared; pass replace=True to redeclare it deliberately"
            )
        self._versioning[agent_type] = versioning

    def versioning_for(self, agent_type: AgentType) -> AgentVersioning:
        """Return the declared versioning.

        Raises
        ------
        KeyError
            When the agent type has no declared identity.
        """
        try:
            return self._versioning[agent_type]
        except KeyError as error:
            raise KeyError(
                f"{agent_type.value} has no declared identity; register it before its first invocation"
            ) from error

    def identity_for(self, agent_type: AgentType, *, provider: str, model: str) -> AgentIdentity:
        """Return the identity to record, binding the declared versions to the live provider and model."""
        declared = self.versioning_for(agent_type)
        return AgentIdentity(
            agent_type=agent_type,
            agent_version=declared.agent_version,
            prompt_version=declared.prompt_version,
            provider=provider,
            model=model,
        )

    def agent_types(self) -> tuple[AgentType, ...]:
        """Return the declared agent types, sorted."""
        return tuple(sorted(self._versioning))


#: Registry used by the control plane unless a component is given its own.
DEFAULT_REGISTRY: Final[AgentRegistry] = AgentRegistry()


class InvocationRecordingError(RuntimeError):
    """Raised when an invocation is recorded out of order, twice, or without saying what happened."""


class AgentInvocationRun:
    """One in-flight agent invocation.

    A run is opened by :meth:`AgentInvocationRecorder.begin`, records what happened, and is closed by
    :meth:`finish`. Every step can be recorded at most once and the steps are ordered — the decision precedes
    the policy evaluation, which precedes the action — so a run cannot silently rewrite its own history.
    """

    def __init__(
        self,
        recorder: AgentInvocationRecorder,
        *,
        agent_type: AgentType,
        invocation_id: Identifier,
        run_id: Identifier,
        incident_id: Identifier,
        identity: AgentIdentity,
        started_at: datetime,
        evidence_ids: Sequence[Identifier],
        correlation_id: Identifier | None,
    ) -> None:
        """Create a run. Instances are produced by :meth:`AgentInvocationRecorder.begin`."""
        self._recorder = recorder
        self.agent_type = agent_type
        self.invocation_id = invocation_id
        self.run_id = run_id
        self.incident_id = incident_id
        self.identity = identity
        self.started_at = started_at
        self.correlation_id = correlation_id
        self._evidence_ids = list(evidence_ids)
        self._decision_id: Identifier | None = None
        self._diagnosis: DiagnosisCategory | None = None
        self._confidence: Confidence | None = None
        self._policy: PolicyVerdict = PolicyVerdict()
        self._action: AgentAction | None = None
        self._invocation: AgentInvocation | None = None
        self._audit_event: AuditEvent | None = None

    @property
    def evidence_ids(self) -> tuple[Identifier, ...]:
        """Return the evidence identifiers recorded for this run."""
        return tuple(self._evidence_ids)

    @property
    def invocation(self) -> AgentInvocation:
        """Return the finished invocation.

        Raises
        ------
        InvocationRecordingError
            When the run has not been finished yet.
        """
        if self._invocation is None:
            raise InvocationRecordingError("the invocation has not been finished")
        return self._invocation

    @property
    def audit_event(self) -> AuditEvent | None:
        """Return the audit event appended for this run, or ``None`` when no trail is configured."""
        return self._audit_event

    def record_decision(
        self,
        diagnosis: DiagnosisCategory,
        confidence: Confidence,
        *,
        decision_id: Identifier | None = None,
    ) -> Self:
        """Record the decision the agent produced, before any policy evaluation."""
        self._ensure_open()
        if self._diagnosis is not None:
            raise InvocationRecordingError("a decision was already recorded for this invocation")
        if self._policy.outcome is not PolicyOutcome.NOT_EVALUATED:
            raise InvocationRecordingError("the decision must be recorded before the policy result")
        self._decision_id = decision_id or new_identifier(
            DECISION_ID_PREFIX, source=self._recorder.id_source
        )
        self._diagnosis = diagnosis
        self._confidence = confidence
        return self

    def record_policy(self, verdict: PolicyVerdict) -> Self:
        """Record the policy verdict that gated this run's action."""
        self._ensure_open()
        if self._policy.outcome is not PolicyOutcome.NOT_EVALUATED:
            raise InvocationRecordingError(
                "a policy result was already recorded for this invocation"
            )
        if verdict.outcome is PolicyOutcome.NOT_EVALUATED:
            raise InvocationRecordingError("record_policy requires an actual policy evaluation")
        self._policy = verdict
        return self

    def record_action(self, action: AgentAction) -> Self:
        """Record the action this run proposed, was denied, or executed."""
        self._ensure_open()
        if self._action is not None:
            raise InvocationRecordingError("an action was already recorded for this invocation")
        if self._policy.outcome is PolicyOutcome.NOT_EVALUATED:
            raise InvocationRecordingError(
                "the policy result must be recorded before the action it applies to"
            )
        self._action = action
        return self

    def finish(
        self, outcome: InvocationOutcome | None = None, *, completed_at: datetime | None = None
    ) -> AgentInvocation:
        """Close the run, record the invocation and append it to the audit trail.

        Parameters
        ----------
        outcome
            How the invocation ended. May be omitted only when the recorded state determines it
            unambiguously; an executed action (policy ``allow``) must state its own outcome.
        completed_at
            Completion time; defaults to the recorder's clock.

        Raises
        ------
        InvocationRecordingError
            When the run was already finished, or when the outcome cannot be inferred.
        """
        self._ensure_open()
        resolved = outcome if outcome is not None else self._infer_outcome()
        invocation = AgentInvocation(
            invocation_id=self.invocation_id,
            run_id=self.run_id,
            incident_id=self.incident_id,
            identity=self.identity,
            started_at=self.started_at,
            completed_at=completed_at or self._recorder.now(),
            evidence_ids=self._evidence_ids,
            decision_id=self._decision_id,
            diagnosis=self._diagnosis,
            confidence=self._confidence,
            policy_result=self._policy,
            action=self._action,
            outcome=resolved,
            correlation_id=self.correlation_id,
        )
        self._invocation = invocation
        self._audit_event = self._recorder.record(invocation)
        return invocation

    def _infer_outcome(self) -> InvocationOutcome:
        """Return the outcome implied by the recorded policy result and diagnosis."""
        if self._policy.outcome is PolicyOutcome.ALLOW:
            raise InvocationRecordingError(
                "an executed action must report its outcome explicitly "
                "(action_succeeded or action_failed)"
            )
        if self._policy.outcome is PolicyOutcome.DENY:
            return InvocationOutcome.DENIED_BY_POLICY
        if self._policy.outcome is PolicyOutcome.REQUIRE_APPROVAL:
            return InvocationOutcome.AWAITING_APPROVAL
        if self._diagnosis is None:
            return InvocationOutcome.AGENT_FAILED
        if self._diagnosis is DiagnosisCategory.INSUFFICIENT_EVIDENCE:
            return InvocationOutcome.INSUFFICIENT_EVIDENCE
        if self._diagnosis is DiagnosisCategory.NO_ACTION_REQUIRED:
            return InvocationOutcome.NO_ACTION
        return InvocationOutcome.DIAGNOSIS_PRODUCED

    def _ensure_open(self) -> None:
        """Reject a write to a run that has already been finished."""
        if self._invocation is not None:
            raise InvocationRecordingError(
                f"invocation {self.invocation_id} is already finished and cannot be changed"
            )


class AgentInvocationRecorder:
    """Records every agent invocation, with or without a durable audit sink attached."""

    def __init__(
        self,
        *,
        registry: AgentRegistry | None = None,
        trail: AuditTrail | None = None,
        clock: Clock | None = None,
        id_source: IdSource | None = None,
    ) -> None:
        """Configure the recorder.

        Parameters
        ----------
        registry
            Declared agent identities; the platform registry is used when omitted.
        trail
            Audit sink. When supplied, every finished invocation is appended to it. The worker injects the
            durable trail; a unit test may run without one and still assert the invocation record.
        clock
            Time source for invocation timestamps.
        id_source
            Random-suffix source for invocation and decision ids.
        """
        self._registry = registry or DEFAULT_REGISTRY
        self._trail = trail
        self._clock: Clock = clock or utc_now
        self._id_source = id_source
        self._invocations: list[AgentInvocation] = []

    @property
    def registry(self) -> AgentRegistry:
        """Return the registry consulted when an invocation opens."""
        return self._registry

    @property
    def trail(self) -> AuditTrail | None:
        """Return the audit sink, or ``None`` when this recorder is not auditing."""
        return self._trail

    @property
    def id_source(self) -> IdSource | None:
        """Return the identifier source, so a run can mint its own decision ids."""
        return self._id_source

    def now(self) -> datetime:
        """Return the current time from the configured clock."""
        return self._clock()

    def begin(
        self,
        *,
        agent_type: AgentType,
        run_id: Identifier,
        incident_id: Identifier,
        provider: str,
        model: str,
        evidence_ids: Sequence[Identifier] = (),
        correlation_id: Identifier | None = None,
        started_at: datetime | None = None,
    ) -> AgentInvocationRun:
        """Open an invocation for one agent run.

        Parameters
        ----------
        agent_type
            Which agent is running. It must be declared in the registry.
        run_id
            Control-loop run this invocation belongs to.
        incident_id
            Incident under investigation.
        provider, model
            The provider and model that will actually answer, recorded as part of the identity.
        evidence_ids
            Identifiers of the evidence handed to the agent.
        correlation_id
            Correlation id shared with the rest of the control loop.
        started_at
            Start time; defaults to the recorder's clock.
        """
        identity = self._registry.identity_for(agent_type, provider=provider, model=model)
        return AgentInvocationRun(
            self,
            agent_type=agent_type,
            invocation_id=new_identifier(INVOCATION_ID_PREFIX, source=self._id_source),
            run_id=run_id,
            incident_id=incident_id,
            identity=identity,
            started_at=started_at or self.now(),
            evidence_ids=evidence_ids,
            correlation_id=correlation_id,
        )

    def record(
        self, invocation: AgentInvocation, *, on_behalf_of: PrincipalId | None = None
    ) -> AuditEvent | None:
        """Store the invocation and, when a trail is configured, append it to the audit log.

        Returns
        -------
        AuditEvent | None
            The appended audit event, or ``None`` when no trail is configured.
        """
        self._invocations.append(invocation)
        if self._trail is None:
            return None
        return self._trail.record_agent_invocation(invocation, on_behalf_of=on_behalf_of)

    def invocations(self) -> tuple[AgentInvocation, ...]:
        """Return every invocation recorded by this recorder, oldest first."""
        return tuple(self._invocations)
