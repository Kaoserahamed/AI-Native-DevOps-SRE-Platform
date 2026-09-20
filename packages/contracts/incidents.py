"""Incident contract and lifecycle state machine.

The lifecycle is the backbone of the platform: incidents move through explicit states, every transition
is auditable, and the invariants here turn "an agent cannot skip a step" into a testable claim rather
than a convention (ADR-0007).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Final, Self

from pydantic import Field, model_validator

from packages.contracts.common import (
    Confidence,
    Identifier,
    LongText,
    PlatformModel,
    ServiceRef,
    Severity,
    ShortText,
    UtcDatetime,
    ValueModel,
)


class IncidentStatus(StrEnum):
    """Every state an incident can be in."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    REOPENED = "reopened"
    CLOSED = "closed"


class CauseCategory(StrEnum):
    """Coarse diagnosis categories shared by the agents, the API and the evaluation suite."""

    DEPLOYMENT_REGRESSION = "deployment_regression"
    DEPENDENCY_FAILURE = "dependency_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CONFIGURATION_ERROR = "configuration_error"
    TRAFFIC_ANOMALY = "traffic_anomaly"
    CODE_DEFECT = "code_defect"
    INFRASTRUCTURE_EVENT = "infrastructure_event"
    UNKNOWN = "unknown"


ALLOWED_TRANSITIONS: Final[Mapping[IncidentStatus, frozenset[IncidentStatus]]] = {
    IncidentStatus.OPEN: frozenset(
        {IncidentStatus.ACKNOWLEDGED, IncidentStatus.INVESTIGATING, IncidentStatus.RESOLVED}
    ),
    IncidentStatus.ACKNOWLEDGED: frozenset(
        {IncidentStatus.INVESTIGATING, IncidentStatus.MITIGATING, IncidentStatus.RESOLVED}
    ),
    IncidentStatus.INVESTIGATING: frozenset({IncidentStatus.MITIGATING, IncidentStatus.RESOLVED}),
    IncidentStatus.MITIGATING: frozenset({IncidentStatus.INVESTIGATING, IncidentStatus.RESOLVED}),
    IncidentStatus.RESOLVED: frozenset({IncidentStatus.CLOSED, IncidentStatus.REOPENED}),
    IncidentStatus.REOPENED: frozenset(
        {
            IncidentStatus.ACKNOWLEDGED,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.MITIGATING,
            IncidentStatus.RESOLVED,
        }
    ),
    # Closed is terminal: a recurrence is a new incident that references the old one.
    IncidentStatus.CLOSED: frozenset(),
}

STATUS_REQUIRED_TIMESTAMPS: Final[Mapping[IncidentStatus, tuple[str, ...]]] = {
    IncidentStatus.OPEN: ("detected_at", "opened_at"),
    IncidentStatus.ACKNOWLEDGED: ("acknowledged_at",),
    IncidentStatus.INVESTIGATING: ("acknowledged_at",),
    IncidentStatus.MITIGATING: ("acknowledged_at",),
    IncidentStatus.RESOLVED: ("acknowledged_at", "resolved_at"),
    IncidentStatus.REOPENED: ("acknowledged_at",),
    IncidentStatus.CLOSED: ("acknowledged_at", "resolved_at", "closed_at"),
}


def can_transition(current: IncidentStatus, target: IncidentStatus) -> bool:
    """Return whether an incident in ``current`` may move to ``target``."""
    return target in ALLOWED_TRANSITIONS[current]


class SuspectedCause(ValueModel):
    """A candidate cause that must cite the evidence supporting it."""

    category: CauseCategory
    description: ShortText
    confidence: Confidence
    evidence_ids: list[Identifier] = Field(
        min_length=1,
        description="Evidence supporting this cause. Uncited causes are not allowed.",
    )


class Incident(PlatformModel):
    """Durable incident record: what broke, what we know, and what was decided."""

    incident_id: Identifier
    title: ShortText
    severity: Severity
    service: ServiceRef
    status: IncidentStatus = IncidentStatus.OPEN
    detected_at: UtcDatetime
    opened_at: UtcDatetime
    acknowledged_at: UtcDatetime | None = None
    mitigated_at: UtcDatetime | None = None
    resolved_at: UtcDatetime | None = None
    closed_at: UtcDatetime | None = None
    triggering_alert_ids: list[Identifier] = Field(default_factory=list)
    evidence_ids: list[Identifier] = Field(default_factory=list)
    suspected_causes: list[SuspectedCause] = Field(default_factory=list)
    confidence: Confidence | None = None
    proposal_ids: list[Identifier] = Field(default_factory=list)
    approval_ids: list[Identifier] = Field(default_factory=list)
    resolution_summary: LongText | None = None
    post_incident_notes: LongText | None = None
    correlation_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        """Enforce timeline ordering, status/timestamp agreement and evidence grounding."""
        if self.opened_at < self.detected_at:
            raise ValueError("opened_at must not be earlier than detected_at")

        timeline = [
            self.detected_at,
            self.opened_at,
            self.acknowledged_at,
            self.mitigated_at,
            self.resolved_at,
            self.closed_at,
        ]
        known = [moment for moment in timeline if moment is not None]
        if known != sorted(known):
            raise ValueError("incident timestamps must be non-decreasing")

        for field_name in STATUS_REQUIRED_TIMESTAMPS[self.status]:
            if getattr(self, field_name) is None:
                raise ValueError(f"status {self.status} requires {field_name}")

        if self.status is IncidentStatus.REOPENED and self.resolved_at is not None:
            raise ValueError("a reopened incident must clear resolved_at until it is resolved again")

        if self.status in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}:
            if self.resolution_summary is None:
                raise ValueError(f"status {self.status} requires a resolution_summary")
        elif self.resolution_summary is not None:
            raise ValueError("resolution_summary may only be set once the incident is resolved")

        if self.post_incident_notes is not None and self.status is not IncidentStatus.CLOSED:
            raise ValueError("post_incident_notes may only be set once the incident is closed")

        if self.status is IncidentStatus.MITIGATING and not (self.proposal_ids or self.approval_ids):
            raise ValueError("a mitigating incident must reference a proposal or an approval")

        if self.suspected_causes and self.confidence is None:
            raise ValueError("confidence is required once suspected causes are recorded")
        if self.confidence is not None and not self.suspected_causes:
            raise ValueError("confidence may only be set alongside suspected causes")

        evidence_ids = set(self.evidence_ids)
        if self.status is not IncidentStatus.OPEN and not evidence_ids:
            raise ValueError("an acknowledged incident must reference at least one evidence item")
        for cause in self.suspected_causes:
            missing = set(cause.evidence_ids) - evidence_ids
            if missing:
                raise ValueError(f"cause cites evidence not attached to the incident: {sorted(missing)}")
        return self
