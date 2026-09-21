"""Append-only audit trail for the control plane.

Every boundary crossing the platform cares about produces one :class:`~packages.contracts.audit.AuditEvent`:
an incident transition, an agent invocation, a policy evaluation, an approval decision, a tool invocation or
an executed action. The log is append-only by construction:

* events are immutable (the contract is frozen), and a stored event is never updated;
* each event carries the digest of the previous event, so a rewritten or reordered history is detectable;
* :meth:`AuditLog.append` refuses an event whose chain position is wrong or whose id already exists.

:class:`AuditTrail` is the writer the rest of the platform uses. It fills in the fields that must never be
optional — actor, timestamp, correlation id, before/after state — and has dedicated writers for the records
the governance model depends on: the approval that authorised an action, the policy verdict that gated it,
and the tool execution that carried it out.

Two sinks ship here: :class:`InMemoryAuditLog` for tests and single-process runs, and
:class:`JsonLineAuditLog` for a durable append-only file. The PostgreSQL-backed store arrives with the
persistence phase and implements the same :class:`AuditLog` protocol.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Protocol, runtime_checkable

from packages.contracts.agents import (
    AgentInvocation,
    InvocationOutcome,
    PolicyOutcome,
    PolicyVerdict,
)
from packages.contracts.audit import AuditActor, AuditEvent, AuditEventType, AuditResult
from packages.contracts.common import (
    MAX_MAPPING_ENTRIES,
    MAX_MAPPING_VALUE_LENGTH,
    ActorType,
    Attributes,
    Digest,
    Identifier,
    PrincipalId,
    canonical_json,
)
from packages.contracts.remediation import Approval, ApprovalDecision
from packages.governance.support import (
    AUDIT_EVENT_PREFIX,
    Clock,
    IdSource,
    new_identifier,
    utc_now,
)

#: Audit result recorded for each invocation outcome.
INVOCATION_RESULTS: Final[Mapping[InvocationOutcome, AuditResult]] = {
    InvocationOutcome.NO_ACTION: AuditResult.SUCCEEDED,
    InvocationOutcome.INSUFFICIENT_EVIDENCE: AuditResult.SUCCEEDED,
    InvocationOutcome.DIAGNOSIS_PRODUCED: AuditResult.SUCCEEDED,
    InvocationOutcome.AWAITING_APPROVAL: AuditResult.SUCCEEDED,
    InvocationOutcome.ACTION_SUCCEEDED: AuditResult.SUCCEEDED,
    InvocationOutcome.ACTION_FAILED: AuditResult.FAILED,
    InvocationOutcome.DENIED_BY_POLICY: AuditResult.DENIED,
    InvocationOutcome.AGENT_FAILED: AuditResult.FAILED,
}


class AuditLogError(RuntimeError):
    """Raised when an audit write would break the append-only chain."""


@runtime_checkable
class AuditLog(Protocol):
    """Append-only sink for audit events."""

    def append(self, event: AuditEvent) -> AuditEvent:
        """Append one event, sealing it onto the current head, and return the stored event."""
        ...

    def events(self) -> tuple[AuditEvent, ...]:
        """Return every stored event, oldest first."""
        ...

    def head(self) -> AuditEvent | None:
        """Return the most recently stored event, or ``None`` when the log is empty."""
        ...

    def verify(self) -> None:
        """Raise :class:`AuditLogError` when the stored chain does not verify."""
        ...


class InMemoryAuditLog:
    """Append-only, hash-chained audit log held in process memory."""

    def __init__(self) -> None:
        """Start an empty log."""
        self._events: list[AuditEvent] = []
        self._event_ids: set[str] = set()

    def append(self, event: AuditEvent) -> AuditEvent:
        """Chain ``event`` onto the head and store it.

        An event that already carries a chain position must carry the correct one: a producer cannot ask the
        log to insert an event in the middle of the history.
        """
        if event.event_id in self._event_ids:
            raise AuditLogError(f"audit event {event.event_id} was already appended")
        expected = self._events[-1].digest if self._events else None
        if event.previous_digest not in (None, expected):
            raise AuditLogError(
                f"audit event {event.event_id} does not chain onto the current head; "
                "events are appended in order, never inserted"
            )
        sealed = (
            event
            if event.previous_digest == expected
            else event.model_copy(update={"previous_digest": expected})
        )
        self._events.append(sealed)
        self._event_ids.add(sealed.event_id)
        return sealed

    def events(self) -> tuple[AuditEvent, ...]:
        """Return every stored event, oldest first."""
        return tuple(self._events)

    def head(self) -> AuditEvent | None:
        """Return the most recently stored event, or ``None`` when the log is empty."""
        return self._events[-1] if self._events else None

    def verify(self) -> None:
        """Raise :class:`AuditLogError` when an event does not chain onto its predecessor."""
        previous: AuditEvent | None = None
        for index, event in enumerate(self._events):
            if not event.follows(previous):
                raise AuditLogError(f"audit chain is broken at index {index} ({event.event_id})")
            previous = event


class JsonLineAuditLog:
    """Append-only audit log stored as one canonical JSON object per line.

    The file is opened in append mode only: an existing line is never rewritten, and a truncated or reordered
    history fails verification on the next load instead of being silently accepted.
    """

    def __init__(self, path: Path) -> None:
        """Open (or create) the log at ``path`` and load the existing chain."""
        self._path = path
        self._memory = InMemoryAuditLog()
        if self._path.exists():
            self._load()

    @property
    def path(self) -> Path:
        """Return the file backing the log."""
        return self._path

    def _load(self) -> None:
        """Load and chain-check the existing lines."""
        text = self._path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                event = AuditEvent.model_validate_json(line)
            except ValueError as error:
                raise AuditLogError(f"audit line {number} is not a valid event: {error}") from error
            self._memory.append(event)
        self._memory.verify()

    def append(self, event: AuditEvent) -> AuditEvent:
        """Seal the event onto the head and append one line to the file."""
        sealed = self._memory.append(event)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = sealed.model_dump(mode="json", exclude_computed_fields=True)
        with self._path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"{canonical_json(payload)}\n")
        return sealed

    def events(self) -> tuple[AuditEvent, ...]:
        """Return every stored event, oldest first."""
        return self._memory.events()

    def head(self) -> AuditEvent | None:
        """Return the most recently stored event, or ``None`` when the log is empty."""
        return self._memory.head()

    def verify(self) -> None:
        """Raise :class:`AuditLogError` when the stored chain does not verify."""
        self._memory.verify()


def bounded_attributes(attributes: Mapping[str, str]) -> dict[str, str]:
    """Return audit attributes with bounded cardinality and value length.

    Raises
    ------
    AuditLogError
        When more attributes are supplied than an event may carry. That is a programming error: a producer
        that needs more keys is recording state that belongs in ``before``/``after``.
    """
    if len(attributes) > MAX_MAPPING_ENTRIES:
        raise AuditLogError(
            f"an audit event carries at most {MAX_MAPPING_ENTRIES} attributes, got {len(attributes)}"
        )
    return {key: value[:MAX_MAPPING_VALUE_LENGTH] for key, value in attributes.items()}


def _state(payload: Mapping[str, Any] | None) -> Attributes | None:
    """Normalise an optional before/after state mapping for the contract."""
    return None if payload is None else dict(payload)


class AuditTrail:
    """The writer of audit events, used by every component that changes or inspects state."""

    def __init__(
        self,
        log: AuditLog | None = None,
        *,
        clock: Clock | None = None,
        id_source: IdSource | None = None,
    ) -> None:
        """Configure the trail.

        Parameters
        ----------
        log
            Sink for the events; an in-memory log is used when none is supplied.
        clock
            Time source; injectable so recorded events are reproducible in tests.
        id_source
            Random-suffix source for event ids; injectable for the same reason.
        """
        self._log: AuditLog = log if log is not None else InMemoryAuditLog()
        self._clock: Clock = clock or utc_now
        self._id_source = id_source

    @property
    def log(self) -> AuditLog:
        """Return the sink the trail writes to."""
        return self._log

    def events(self) -> tuple[AuditEvent, ...]:
        """Return every audit event recorded so far, oldest first."""
        return self._log.events()

    def head(self) -> AuditEvent | None:
        """Return the most recent audit event, or ``None`` when nothing is recorded."""
        return self._log.head()

    def verify(self) -> None:
        """Raise :class:`AuditLogError` when the recorded chain does not verify."""
        self._log.verify()

    def record(
        self,
        *,
        event_type: AuditEventType,
        actor: AuditActor,
        subject: Identifier,
        result: AuditResult,
        correlation_id: Identifier,
        incident_id: Identifier | None = None,
        approval_id: Identifier | None = None,
        action_hash: Digest | None = None,
        tool: Identifier | None = None,
        before: Mapping[str, Any] | None = None,
        after: Mapping[str, Any] | None = None,
        attributes: Mapping[str, str] | None = None,
    ) -> AuditEvent:
        """Append one event and return the stored (chained) record."""
        event = AuditEvent(
            event_id=new_identifier(AUDIT_EVENT_PREFIX, source=self._id_source),
            occurred_at=self._clock(),
            actor=actor,
            event_type=event_type,
            subject=subject,
            result=result,
            correlation_id=correlation_id,
            incident_id=incident_id,
            approval_id=approval_id,
            action_hash=action_hash,
            tool=tool,
            before=_state(before),
            after=_state(after),
            attributes=bounded_attributes(attributes or {}),
        )
        return self._log.append(event)

    def record_agent_invocation(
        self, invocation: AgentInvocation, *, on_behalf_of: PrincipalId | None = None
    ) -> AuditEvent:
        """Record one agent invocation with its full identity, decision, policy result and action."""
        identity = invocation.identity
        action = invocation.action
        verdict = invocation.policy_result
        return self.record(
            event_type=AuditEventType.AGENT_INVOKED,
            actor=AuditActor(
                actor_type=ActorType.AGENT,
                actor_id=identity.actor_id,
                on_behalf_of=on_behalf_of,
            ),
            subject=invocation.incident_id,
            result=INVOCATION_RESULTS[invocation.outcome],
            correlation_id=invocation.correlation_id or invocation.run_id,
            incident_id=invocation.incident_id,
            approval_id=action.approval_id if action else None,
            action_hash=action.action_hash if action else None,
            before={
                "started_at": invocation.started_at.isoformat(),
                "evidence_count": len(invocation.evidence_ids),
                "invocation_id": invocation.invocation_id,
            },
            after={
                "completed_at": invocation.completed_at.isoformat(),
                "outcome": invocation.outcome.value,
                "diagnosis": invocation.diagnosis.value if invocation.diagnosis else None,
                "policy_outcome": verdict.outcome.value,
                "action_hash": action.action_hash if action else None,
                "evidence_ids": list(invocation.evidence_ids),
            },
            attributes=_invocation_attributes(invocation),
        )

    def record_policy_evaluation(
        self,
        verdict: PolicyVerdict,
        *,
        subject: Identifier,
        actor: AuditActor,
        correlation_id: Identifier,
        incident_id: Identifier | None = None,
        action_hash: Digest | None = None,
    ) -> AuditEvent:
        """Record the policy verdict that gated an action."""
        return self.record(
            event_type=AuditEventType.POLICY_EVALUATED,
            actor=actor,
            subject=subject,
            result=_verdict_result(verdict),
            correlation_id=correlation_id,
            incident_id=incident_id,
            action_hash=action_hash,
            before={"outcome": "pending"},
            after={
                "outcome": verdict.outcome.value,
                "required_approvals": verdict.required_approvals,
                "violations": list(verdict.violations),
            },
            attributes={
                "policy_outcome": verdict.outcome.value,
                "required_approvals": str(verdict.required_approvals),
                "violation_count": str(len(verdict.violations)),
                "evaluated_at": verdict.evaluated_at.isoformat()
                if verdict.evaluated_at
                else "none",
            },
        )

    def record_approval(self, approval: Approval) -> AuditEvent:
        """Record a human approval decision, bound to the action hash it authorises."""
        actor = AuditActor(
            actor_type=approval.approver.actor_type,
            actor_id=approval.approver.identity,
        )
        return self.record(
            event_type=AuditEventType.APPROVAL_DECIDED,
            actor=actor,
            subject=approval.approval_id,
            result=(
                AuditResult.SUCCEEDED
                if approval.decision is ApprovalDecision.APPROVED
                else AuditResult.DENIED
            ),
            correlation_id=approval.correlation_id or approval.incident_id,
            incident_id=approval.incident_id,
            approval_id=approval.approval_id,
            action_hash=approval.action_hash,
            before={"decision": "pending"},
            after={
                "decision": approval.decision.value,
                "proposal_id": approval.proposal_id,
                "decided_at": approval.decided_at.isoformat(),
                "expires_at": approval.expires_at.isoformat(),
                "consumed_at": approval.consumed_at.isoformat() if approval.consumed_at else None,
            },
            attributes={
                "decision": approval.decision.value,
                "proposal_id": approval.proposal_id,
                "comment": approval.comment or "none",
            },
        )

    def record_tool_invocation(
        self,
        *,
        actor: AuditActor,
        tool: Identifier,
        arguments_digest: Digest,
        decision: str,
        result: AuditResult,
        correlation_id: Identifier,
        subject: Identifier | None = None,
        incident_id: Identifier | None = None,
        before: Mapping[str, Any] | None = None,
        after: Mapping[str, Any] | None = None,
        error: str | None = None,
    ) -> AuditEvent:
        """Record one tool invocation: the authorization decision and, when it ran, the execution result."""
        return self.record(
            event_type=AuditEventType.TOOL_INVOKED,
            actor=actor,
            subject=subject or tool,
            result=result,
            correlation_id=correlation_id,
            incident_id=incident_id,
            tool=tool,
            before=before,
            after=after,
            attributes={
                "decision": decision,
                "arguments_digest": arguments_digest,
                "error": error or "none",
            },
        )


def _verdict_result(verdict: PolicyVerdict) -> AuditResult:
    """Map a policy outcome onto the audit result vocabulary."""
    if verdict.outcome is PolicyOutcome.DENY:
        return AuditResult.DENIED
    return AuditResult.SUCCEEDED


def _invocation_attributes(invocation: AgentInvocation) -> dict[str, str]:
    """Return the flat audit attributes the governance document requires for every invocation."""
    identity = invocation.identity
    action = invocation.action
    verdict = invocation.policy_result
    return {
        "agent_type": identity.agent_type.value,
        "agent_version": identity.agent_version,
        "prompt_version": identity.prompt_version,
        "provider": identity.provider,
        "model": identity.model,
        "invocation_id": invocation.invocation_id,
        "run_id": invocation.run_id,
        "outcome": invocation.outcome.value,
        "decision_id": invocation.decision_id or "none",
        "diagnosis": invocation.diagnosis.value if invocation.diagnosis else "none",
        "confidence": (
            f"{invocation.confidence:.4f}" if invocation.confidence is not None else "none"
        ),
        "policy_result": verdict.outcome.value,
        "required_approvals": str(verdict.required_approvals),
        "action": action.category.value if action else "none",
        "action_hash": action.action_hash if action else "none",
        "approval_id": (action.approval_id or "none") if action else "none",
        "evidence_count": str(len(invocation.evidence_ids)),
    }
