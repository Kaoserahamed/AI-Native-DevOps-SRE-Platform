"""Audit event contract: append-only, hash-chained records of who did what.

Every boundary crossing in the architecture produces one of these. The record is append-only by
construction: the store never updates a row, and each event carries the digest of the previous event,
so a tampered or reordered history is detectable (chain verification is part of the audit tests).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from packages.contracts.common import (
    MAX_MAPPING_ENTRIES,
    ActorType,
    Attributes,
    Digest,
    Identifier,
    PlatformModel,
    PrincipalId,
    UtcDatetime,
    ValueModel,
    canonical_json,
    sha256_digest,
)

MAX_STATE_BYTES: Final[int] = 4_096


class AuditEventType(StrEnum):
    """Auditable event types produced by the control plane."""

    INCIDENT_OPENED = "incident_opened"
    INCIDENT_TRANSITIONED = "incident_transitioned"
    EVIDENCE_COLLECTED = "evidence_collected"
    AGENT_INVOKED = "agent_invoked"
    PROPOSAL_CREATED = "proposal_created"
    POLICY_EVALUATED = "policy_evaluated"
    APPROVAL_DECIDED = "approval_decided"
    ACTION_EXECUTED = "action_executed"
    TOOL_INVOKED = "tool_invoked"


class AuditResult(StrEnum):
    """Outcome of the recorded operation."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"


class AuditActor(ValueModel):
    """Who or what performed the operation."""

    actor_type: ActorType
    actor_id: PrincipalId = Field(
        description="Human email address, or agent identifier such as incident_agent@0.1.0."
    )
    on_behalf_of: PrincipalId | None = Field(
        default=None, description="Set when an agent acts during a workflow started by a human."
    )


class AuditEvent(PlatformModel):
    """One immutable audit record."""

    event_id: Identifier
    occurred_at: UtcDatetime
    actor: AuditActor
    event_type: AuditEventType
    subject: Identifier = Field(
        description="Primary object the event is about, such as an incident id."
    )
    result: AuditResult
    correlation_id: Identifier
    incident_id: Identifier | None = None
    approval_id: Identifier | None = None
    action_hash: Digest | None = None
    tool: Identifier | None = None
    before: Attributes | None = None
    after: Attributes | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    previous_digest: Digest | None = Field(
        default=None,
        description="Digest of the previous event in the chain; null for the first event.",
    )

    @model_validator(mode="after")
    def validate_sizes(self) -> Self:
        """Bound the recorded state so the audit trail cannot become an unbounded data dump."""
        for name in ("before", "after"):
            state = getattr(self, name)
            if state is not None and len(canonical_json(state).encode("utf-8")) > MAX_STATE_BYTES:
                raise ValueError(f"{name} state must not exceed {MAX_STATE_BYTES} bytes")
        if len(self.attributes) > MAX_MAPPING_ENTRIES:
            raise ValueError(f"at most {MAX_MAPPING_ENTRIES} attributes are allowed")
        return self

    def digest_payload(self) -> dict[str, object]:
        """Return the exact payload that is hashed for the chain digest."""
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "occurred_at": self.occurred_at.isoformat(),
            "actor": self.actor.model_dump(mode="json"),
            "event_type": self.event_type.value,
            "subject": self.subject,
            "result": self.result.value,
            "correlation_id": self.correlation_id,
            "incident_id": self.incident_id,
            "approval_id": self.approval_id,
            "action_hash": self.action_hash,
            "tool": self.tool,
            "before": self.before,
            "after": self.after,
            "attributes": self.attributes,
            "previous_digest": self.previous_digest,
        }

    @computed_field(  # type: ignore[prop-decorator]
        description="Chain digest covering the event content and the previous event digest."
    )
    @property
    def digest(self) -> str:
        """Return the sha256 digest that the next event must reference."""
        return sha256_digest(self.digest_payload())

    def follows(self, previous: AuditEvent | None) -> bool:
        """Return whether this event correctly chains onto ``previous``."""
        expected = None if previous is None else previous.digest
        return self.previous_digest == expected


#: Maps the simple action strings used at API boundaries to the canonical
#: event types the audit trail stores.  Several boundaries collapse to
#: ``INCIDENT_TRANSITIONED`` because the trail records lifecycle movement,
#: not the specific verb the caller used.
_ACTION_TO_EVENT_TYPE: Final[dict[str, AuditEventType]] = {
    "incident.create": AuditEventType.INCIDENT_OPENED,
    "incident.update": AuditEventType.INCIDENT_TRANSITIONED,
    "incident.acknowledge": AuditEventType.INCIDENT_TRANSITIONED,
    "incident.investigate": AuditEventType.INCIDENT_TRANSITIONED,
    "incident.mitigate": AuditEventType.INCIDENT_TRANSITIONED,
    "incident.resolve": AuditEventType.INCIDENT_TRANSITIONED,
    "incident.reopen": AuditEventType.INCIDENT_TRANSITIONED,
    "incident.close": AuditEventType.INCIDENT_TRANSITIONED,
    "evidence.attach": AuditEventType.EVIDENCE_COLLECTED,
}

#: Maps the outcome strings used at API boundaries to the typed ``AuditResult``.
_OUTCOME_TO_RESULT: Final[dict[str, AuditResult]] = {
    "success": AuditResult.SUCCEEDED,
    "failed": AuditResult.FAILED,
    "denied": AuditResult.DENIED,
}


class AuditEntry(BaseModel):
    """Convenience model for audit records created at API boundaries.

    API endpoints create audit entries using field names that are clearer in
    that context (``audit_id``, ``timestamp``, ``action``).  :meth:`to_event`
    converts them to the canonical :class:`AuditEvent` that the persistence
    layer stores, mapping free-form action strings to typed
    :class:`AuditEventType` values and sealing the chain digests.
    """

    model_config = ConfigDict(extra="forbid")

    audit_id: Identifier
    timestamp: UtcDatetime
    actor_type: ActorType
    actor_id: PrincipalId
    action: str
    resource_type: str
    resource_id: Identifier
    outcome: str
    details: Attributes | None = None

    def to_event(self) -> AuditEvent:
        """Convert to a canonical :class:`AuditEvent` for persistence."""
        result = _OUTCOME_TO_RESULT.get(self.outcome, AuditResult.FAILED)
        return AuditEvent(
            event_id=self.audit_id,
            occurred_at=self.timestamp,
            actor=AuditActor(
                actor_type=self.actor_type,
                actor_id=self.actor_id,
            ),
            event_type=_ACTION_TO_EVENT_TYPE.get(
                self.action, AuditEventType.INCIDENT_TRANSITIONED
            ),
            subject=self.resource_id,
            result=result,
            correlation_id=f"corr-{self.resource_id}",
            incident_id=self.resource_id if self.resource_type == "incident" else None,
            attributes={
                "action": self.action,
                "resource_type": self.resource_type,
            },
            after=self.details,
        )
