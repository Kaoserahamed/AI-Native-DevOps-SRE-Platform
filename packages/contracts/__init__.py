"""Versioned platform contracts.

The public surface of this package is the set of wire-level schemas that services, agents, adapters and
the API share:

* :class:`~packages.contracts.alerts.Alert`
* :class:`~packages.contracts.evidence.Evidence`
* :class:`~packages.contracts.incidents.Incident` (with its lifecycle state machine)
* :class:`~packages.contracts.agents.AgentDecision` and
  :class:`~packages.contracts.agents.AgentInvocation` (agent identity, decision, policy result, action and
  outcome for every invocation)
* :class:`~packages.contracts.remediation.RemediationProposal` and
  :class:`~packages.contracts.remediation.Approval`
* :class:`~packages.contracts.audit.AuditEvent`
* :class:`~packages.contracts.errors.ApiError`

Every payload carries ``schema_version`` (currently ``v1``). The committed JSON Schemas under
``packages/contracts/schemas/<version>/`` are the machine-readable snapshot compared in CI, so a change
to a schema is a deliberate, reviewed act rather than an accident.
"""

from __future__ import annotations

from packages.contracts.agents import (
    ACTION_OUTCOMES,
    AgentAction,
    AgentDecision,
    AgentIdentity,
    AgentInvocation,
    AgentType,
    AgentUsage,
    Citation,
    DiagnosisCategory,
    InvocationOutcome,
    PolicyOutcome,
    PolicyVerdict,
)
from packages.contracts.alerts import Alert, AlertSource
from packages.contracts.audit import AuditActor, AuditEvent, AuditEventType, AuditResult
from packages.contracts.common import (
    SCHEMA_VERSION,
    ActorType,
    Confidence,
    Environment,
    Identifier,
    PlatformModel,
    PrincipalId,
    ServiceRef,
    Severity,
    UtcDatetime,
    ValueModel,
    VersionRef,
    canonical_json,
    sha256_digest,
)
from packages.contracts.errors import ApiError, ErrorDetail
from packages.contracts.evidence import (
    Evidence,
    EvidenceCollector,
    EvidenceKind,
    TimeWindow,
)
from packages.contracts.incidents import (
    ALLOWED_TRANSITIONS,
    CauseCategory,
    Incident,
    IncidentStatus,
    SuspectedCause,
    can_transition,
)
from packages.contracts.remediation import (
    ActionTarget,
    Approval,
    ApprovalDecision,
    Approver,
    BlastRadius,
    RemediationCategory,
    RemediationProposal,
    RiskLevel,
)
from packages.contracts.versioning import (
    CONTRACT_MODELS,
    export_schemas,
    schema_document,
    schema_snapshot_directory,
)

__all__ = [
    "ACTION_OUTCOMES",
    "ALLOWED_TRANSITIONS",
    "CONTRACT_MODELS",
    "SCHEMA_VERSION",
    "ActionTarget",
    "ActorType",
    "AgentAction",
    "AgentDecision",
    "AgentIdentity",
    "AgentInvocation",
    "AgentType",
    "AgentUsage",
    "Alert",
    "AlertSource",
    "ApiError",
    "Approval",
    "ApprovalDecision",
    "Approver",
    "AuditActor",
    "AuditEvent",
    "AuditEventType",
    "AuditResult",
    "BlastRadius",
    "CauseCategory",
    "Citation",
    "Confidence",
    "DiagnosisCategory",
    "Environment",
    "ErrorDetail",
    "Evidence",
    "EvidenceCollector",
    "EvidenceKind",
    "Identifier",
    "Incident",
    "IncidentStatus",
    "InvocationOutcome",
    "PlatformModel",
    "PolicyOutcome",
    "PolicyVerdict",
    "PrincipalId",
    "RemediationCategory",
    "RemediationProposal",
    "RiskLevel",
    "ServiceRef",
    "Severity",
    "SuspectedCause",
    "TimeWindow",
    "UtcDatetime",
    "ValueModel",
    "VersionRef",
    "can_transition",
    "canonical_json",
    "export_schemas",
    "schema_document",
    "schema_snapshot_directory",
    "sha256_digest",
]
