"""Remediation proposal contract.

A proposal is a *candidate* action: it carries rationale, evidence, expected impact, blast radius, a
rollback plan and the permissions it would need. The canonical ``action_hash`` is the linchpin of the
governance model (ADR-0007): approvals, idempotency keys and execution checks all bind to it, so an
approval for one action can never authorise a different one.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Final, Self

from pydantic import Field, StringConstraints, computed_field, model_validator

from packages.contracts.common import (
    MAX_MAPPING_ENTRIES,
    ActorType,
    Confidence,
    Digest,
    Environment,
    Identifier,
    LongText,
    MachineName,
    PlatformModel,
    PrincipalId,
    UtcDatetime,
    ValueModel,
    sha256_digest,
)

MAX_PERMISSION_LENGTH: Final[int] = 120
MAX_APPROVAL_WINDOW: Final[timedelta] = timedelta(hours=4)

Permission = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=MAX_PERMISSION_LENGTH)
]
Revision = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class RemediationCategory(StrEnum):
    """The only action classes the platform may ever propose."""

    RESTART_OR_ROLLOUT = "restart_or_rollout"
    ROLLBACK = "rollback"
    CONFIGURATION_CHANGE = "configuration_change"
    RESOURCE_ADJUSTMENT = "resource_adjustment"
    CODE_FIX = "code_fix"
    ALERT_TUNING = "alert_tuning"
    COST_OPTIMIZATION = "cost_optimization"


class BlastRadius(StrEnum):
    """How far an action can reach; drives the required policy result."""

    SINGLE_POD = "single_pod"
    WORKLOAD = "workload"
    NAMESPACE = "namespace"
    CLUSTER = "cluster"
    REPOSITORY_ONLY = "repository_only"


class RiskLevel(StrEnum):
    """Assessed risk of executing the proposal."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActionTarget(ValueModel):
    """The exact object an action applies to."""

    environment: Environment
    namespace: MachineName
    workload: MachineName
    resource_kind: MachineName = "deployment"
    revision: Revision | None = Field(
        default=None,
        description="Image digest, commit SHA or manifest revision the action targets.",
    )


class RemediationProposal(PlatformModel):
    """A governed remediation candidate."""

    proposal_id: Identifier
    incident_id: Identifier
    category: RemediationCategory
    target: ActionTarget
    rationale: LongText
    evidence_ids: list[Identifier] = Field(min_length=1)
    expected_impact: LongText
    blast_radius: BlastRadius
    rollback_plan: LongText
    confidence: Confidence
    required_permissions: list[Permission] = Field(min_length=1)
    risk: RiskLevel
    parameters: dict[str, str] = Field(default_factory=dict)
    created_at: UtcDatetime
    expires_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def validate_parameters(self) -> Self:
        """Keep the parameter map small and deterministic: it is part of the action hash."""
        if len(self.parameters) > MAX_MAPPING_ENTRIES:
            raise ValueError(f"at most {MAX_MAPPING_ENTRIES} parameters are allowed")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")
        return self

    @computed_field(  # type: ignore[prop-decorator]
        description="Canonical digest of the action; approvals and idempotency keys bind to this value."
    )
    @property
    def action_hash(self) -> str:
        """Return a deterministic digest of the action, independent of its narrative fields."""
        return sha256_digest(
            {
                "category": self.category.value,
                "target": self.target.model_dump(mode="json"),
                "parameters": self.parameters,
            }
        )


class ApprovalDecision(StrEnum):
    """The only two outcomes of a human decision."""

    APPROVED = "approved"
    REJECTED = "rejected"


class Approver(ValueModel):
    """The human principal that decided. Agents and automation may never appear here."""

    actor_type: ActorType = ActorType.HUMAN
    identity: PrincipalId = Field(
        description="Authenticated principal, for example an email address."
    )

    @model_validator(mode="after")
    def validate_human(self) -> Self:
        """Only a human principal may approve a production change."""
        if self.actor_type is not ActorType.HUMAN:
            raise ValueError("approvals must come from a human principal")
        return self


class Approval(PlatformModel):
    """A single-use, expiring decision bound to one action hash."""

    approval_id: Identifier
    incident_id: Identifier
    proposal_id: Identifier
    action_hash: Digest
    approver: Approver
    decision: ApprovalDecision
    comment: LongText | None = None
    decided_at: UtcDatetime
    expires_at: UtcDatetime
    consumed_at: UtcDatetime | None = None
    correlation_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        """Approvals are short-lived and are consumed at most once."""
        if self.expires_at <= self.decided_at:
            raise ValueError("expires_at must be later than decided_at")
        if self.expires_at - self.decided_at > MAX_APPROVAL_WINDOW:
            raise ValueError(f"approvals must expire within {MAX_APPROVAL_WINDOW}")
        if self.decision is ApprovalDecision.REJECTED and self.consumed_at is not None:
            raise ValueError("a rejected approval is never consumed by an execution")
        if self.consumed_at is not None and self.consumed_at < self.decided_at:
            raise ValueError("consumed_at must not be earlier than decided_at")
        return self

    def is_usable(self, action_hash: str, now: datetime | None = None) -> bool:
        """Return whether this approval authorises ``action_hash`` at ``now``."""
        moment = (now or datetime.now(tz=UTC)).astimezone(UTC)
        return (
            self.decision is ApprovalDecision.APPROVED
            and self.action_hash == action_hash
            and self.consumed_at is None
            and moment < self.expires_at
        )
