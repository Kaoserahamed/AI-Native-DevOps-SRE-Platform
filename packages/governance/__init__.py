"""Agent safety, governance and auditability (Phase 12, Tasks 12.1 - 12.4).

This package is the part of the platform that makes the *safety* claims testable rather than aspirational:

| Module | Task | Responsibility |
| --- | --- | --- |
| :mod:`packages.governance.identity` | 12.1 | Declared agent identity (type, version, prompt version) and the invocation recorder |
| :mod:`packages.governance.prompts` | 12.2 | Untrusted-input handling: fenced evidence, neutralized override/injection text, bounded prompts |
| :mod:`packages.governance.tools` | 12.3 | Tool allowlist, per-tool argument limits, validated structured tool output |
| :mod:`packages.governance.authorization` | 12.3 | Deny-by-default authorization, per-agent permission sets, approval before production mutation |
| :mod:`packages.governance.audit` | 12.4 | Append-only, hash-chained audit log and the writers for invocations, policy verdicts, approvals and tool calls |
| :mod:`packages.governance.support` | — | Injectable clock and identifier source, so recorded history is reproducible in tests |

The contracts the records conform to live in :mod:`packages.contracts.agents` (invocation) and
:mod:`packages.contracts.audit` (audit event).
"""

from __future__ import annotations

from packages.governance.audit import (
    INVOCATION_RESULTS,
    AuditLog,
    AuditLogError,
    AuditTrail,
    InMemoryAuditLog,
    JsonLineAuditLog,
    bounded_attributes,
)
from packages.governance.authorization import (
    AGENT_PERMISSIONS,
    DECISION_RESULTS,
    AuthorizationResult,
    ToolAuthorizer,
    ToolDecision,
    ToolExecution,
    ToolRequest,
)
from packages.governance.identity import (
    AGENT_VERSION,
    DEFAULT_REGISTRY,
    DEFAULT_VERSIONING,
    AgentInvocationRecorder,
    AgentInvocationRun,
    AgentRegistry,
    AgentVersioning,
    InvocationRecordingError,
)
from packages.governance.prompts import (
    DATA_BOUNDARY_NOTICE,
    INCIDENT_ANALYSIS_PROMPT_VERSION,
    REDACTION_MARKER,
    TRUNCATION_MARKER,
    UNTRUSTED_CLOSE,
    UNTRUSTED_OPEN,
    EvidenceItem,
    EvidenceSnippet,
    PromptBuild,
    Redaction,
    SanitizedText,
    build_evidence_prompt,
    sanitize_markdown_for_rendering,
    sanitize_untrusted_text,
)
from packages.governance.support import (
    AUDIT_EVENT_PREFIX,
    INVOCATION_ID_PREFIX,
    Clock,
    IdSource,
    new_identifier,
    utc_now,
)
from packages.governance.tools import (
    ACTION_HASH_ARGUMENT,
    TOOL_DEFINITIONS,
    AgentTool,
    ToolDefinition,
    ToolKind,
    ToolOutput,
    ToolOutputItem,
    ToolOutputValidationError,
    ToolPermission,
    is_action_hash,
    tool_call_digest,
    validate_tool_arguments,
    validate_tool_output,
)

__all__ = [
    "ACTION_HASH_ARGUMENT",
    "AGENT_PERMISSIONS",
    "AGENT_VERSION",
    "AUDIT_EVENT_PREFIX",
    "DATA_BOUNDARY_NOTICE",
    "DECISION_RESULTS",
    "DEFAULT_REGISTRY",
    "DEFAULT_VERSIONING",
    "INCIDENT_ANALYSIS_PROMPT_VERSION",
    "INVOCATION_ID_PREFIX",
    "INVOCATION_RESULTS",
    "REDACTION_MARKER",
    "TOOL_DEFINITIONS",
    "TRUNCATION_MARKER",
    "UNTRUSTED_CLOSE",
    "UNTRUSTED_OPEN",
    "AgentInvocationRecorder",
    "AgentInvocationRun",
    "AgentRegistry",
    "AgentTool",
    "AgentVersioning",
    "AuditLog",
    "AuditLogError",
    "AuditTrail",
    "AuthorizationResult",
    "Clock",
    "EvidenceItem",
    "EvidenceSnippet",
    "IdSource",
    "InMemoryAuditLog",
    "InvocationRecordingError",
    "JsonLineAuditLog",
    "PromptBuild",
    "Redaction",
    "SanitizedText",
    "ToolAuthorizer",
    "ToolDecision",
    "ToolDefinition",
    "ToolExecution",
    "ToolKind",
    "ToolOutput",
    "ToolOutputItem",
    "ToolOutputValidationError",
    "ToolPermission",
    "ToolRequest",
    "bounded_attributes",
    "build_evidence_prompt",
    "is_action_hash",
    "new_identifier",
    "sanitize_markdown_for_rendering",
    "sanitize_untrusted_text",
    "tool_call_digest",
    "utc_now",
    "validate_tool_arguments",
    "validate_tool_output",
]
