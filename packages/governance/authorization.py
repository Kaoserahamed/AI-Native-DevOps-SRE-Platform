"""Least-privilege tool authorization and auditing (Task 12.3).

Every tool call passes through :class:`ToolAuthorizer` before it reaches an adapter, and every decision is
recorded. The rules are deliberately boring and deny-by-default:

1. **Allowlist.** A tool that is not declared in the catalogue cannot run.
2. **Per-agent permission sets.** An agent may only use a tool whose permission it explicitly holds, and the
   shipped permission sets are read-only except for the reviewable artifacts a remediation agent opens (an
   issue, a pull request). No shipped agent holds :attr:`ToolPermission.MUTATE_WORKLOAD`, so production
   mutation is disabled for every agent out of the box.
3. **Bounded arguments.** Unexpected, non-scalar, empty or over-long arguments are refused before the tool
   runs.
4. **Approval before production mutation.** A mutating call in production requires a human approval bound to
   the exact action hash in the call, and the approval must be usable: not rejected, not expired, not already
   consumed. A replayed approval therefore authorises nothing.
5. **Validated answers.** A tool answer is validated against the declared envelope, so malformed output never
   reaches a prompt or a decision.

The decision and the execution are separate audit events, so a denial can never be confused with a failed
execution: ``deny``/``require_approval`` produce one event with ``result=denied``, an allowed call produces a
second event carrying the answer digest.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

from packages.contracts.agents import AgentType
from packages.contracts.audit import AuditActor, AuditEvent, AuditResult
from packages.contracts.common import ActorType, Digest, Environment, Identifier, PrincipalId
from packages.contracts.remediation import Approval, ApprovalDecision
from packages.governance.audit import AuditTrail
from packages.governance.tools import (
    ACTION_HASH_ARGUMENT,
    TOOL_DEFINITIONS,
    AgentTool,
    ToolDefinition,
    ToolKind,
    ToolOutput,
    ToolPermission,
    is_action_hash,
    tool_call_digest,
    validate_tool_arguments,
    validate_tool_output,
)


class ToolDecision(StrEnum):
    """Authorization decision for one tool invocation."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


#: Permissions each agent holds. Read-only by default; no agent may mutate a workload until an operator
#: grants it here deliberately.
AGENT_PERMISSIONS: Final[Mapping[AgentType, frozenset[ToolPermission]]] = {
    AgentType.ANOMALY_AGENT: frozenset({ToolPermission.READ_TELEMETRY}),
    AgentType.INCIDENT_AGENT: frozenset(
        {ToolPermission.READ_TELEMETRY, ToolPermission.READ_DEPLOYMENT_HISTORY}
    ),
    AgentType.REMEDIATION_AGENT: frozenset(
        {
            ToolPermission.READ_TELEMETRY,
            ToolPermission.READ_DEPLOYMENT_HISTORY,
            ToolPermission.WRITE_ISSUE,
            ToolPermission.WRITE_PULL_REQUEST,
        }
    ),
    AgentType.COST_AGENT: frozenset(
        {ToolPermission.READ_TELEMETRY, ToolPermission.READ_DEPLOYMENT_HISTORY}
    ),
}

DECISION_RESULTS: Final[Mapping[ToolDecision, AuditResult]] = {
    ToolDecision.ALLOW: AuditResult.SUCCEEDED,
    ToolDecision.REQUIRE_APPROVAL: AuditResult.DENIED,
    ToolDecision.DENY: AuditResult.DENIED,
}

#: Arguments that describe the object a state-changing call targets, recorded as before/after state.
TARGET_ARGUMENTS: Final[tuple[str, ...]] = ("namespace", "workload", "kind", "revision")


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """One request to use a tool."""

    agent_type: AgentType
    agent_version: str
    tool: AgentTool
    arguments: Mapping[str, object] = field(default_factory=dict)
    environment: Environment = Environment.PRODUCTION
    approval: Approval | None = None
    incident_id: Identifier | None = None
    correlation_id: Identifier | None = None
    on_behalf_of: PrincipalId | None = None

    @property
    def actor(self) -> AuditActor:
        """Return the audit actor for this request."""
        return AuditActor(
            actor_type=ActorType.AGENT,
            actor_id=f"{self.agent_type.value}@{self.agent_version}",
            on_behalf_of=self.on_behalf_of,
        )

    @property
    def action_hash(self) -> str | None:
        """Return the action hash the call is bound to, when it carries one."""
        value = self.arguments.get(ACTION_HASH_ARGUMENT)
        return value if isinstance(value, str) else None

    @property
    def target(self) -> dict[str, str]:
        """Return the target arguments of a state-changing call, for the audit before/after state."""
        return {
            name: str(self.arguments[name]) for name in TARGET_ARGUMENTS if name in self.arguments
        }


@dataclass(frozen=True, slots=True)
class AuthorizationResult:
    """The decision on one tool invocation, with the reasons and the record that proves it."""

    decision: ToolDecision
    definition: ToolDefinition | None
    reasons: tuple[str, ...]
    arguments_digest: Digest
    audit_event: AuditEvent | None = None

    @property
    def allowed(self) -> bool:
        """Return whether the call may run."""
        return self.decision is ToolDecision.ALLOW

    def explain(self) -> str:
        """Return a one-line explanation, for a log line or a denial message."""
        return "; ".join(self.reasons) or "allowed"


@dataclass(frozen=True, slots=True)
class ToolExecution:
    """The outcome of one tool call, including the validated answer and its audit records."""

    request: ToolRequest
    authorization: AuthorizationResult
    output: ToolOutput | None = None
    error: str | None = None
    events: tuple[AuditEvent, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return whether the tool ran and returned a valid answer."""
        return self.output is not None


class ToolAuthorizer:
    """The least-privilege gate in front of every agent tool call."""

    def __init__(
        self,
        *,
        permissions: Mapping[AgentType, frozenset[ToolPermission]] | None = None,
        catalogue: Mapping[AgentTool, ToolDefinition] | None = None,
        trail: AuditTrail | None = None,
    ) -> None:
        """Configure the authorizer.

        Parameters
        ----------
        permissions
            Per-agent permission sets; the shipped read-only defaults are used when omitted.
        catalogue
            Declared tools. Passing a restricted catalogue is how an operator disables a tool.
        trail
            Audit sink. When supplied, every decision and every execution is recorded.
        """
        self._permissions = dict(permissions or AGENT_PERMISSIONS)
        self._catalogue = dict(catalogue or TOOL_DEFINITIONS)
        self._trail = trail

    @property
    def trail(self) -> AuditTrail | None:
        """Return the audit sink, or ``None`` when this authorizer is not auditing."""
        return self._trail

    def permissions_for(self, agent_type: AgentType) -> frozenset[ToolPermission]:
        """Return the permissions granted to an agent type."""
        return self._permissions.get(agent_type, frozenset())

    def authorize(self, request: ToolRequest) -> AuthorizationResult:
        """Decide whether the request may run, and record the decision."""
        decision, reasons = self._decide(request)
        return AuthorizationResult(
            decision=decision,
            definition=self._catalogue.get(request.tool),
            reasons=reasons,
            arguments_digest=tool_call_digest(request.tool, request.arguments),
            audit_event=self._audit_decision(request, decision, reasons),
        )

    def invoke(
        self,
        request: ToolRequest,
        executor: Callable[[ToolRequest], Mapping[str, Any]],
    ) -> ToolExecution:
        """Authorize, run and audit one tool call.

        The executor is never called unless the decision is ``allow``, and the answer it returns is validated
        before it is handed back, so an unauthorized call cannot happen and a malformed answer cannot
        propagate to a prompt, a decision or an evidence record.
        """
        result = self.authorize(request)
        events: list[AuditEvent] = [result.audit_event] if result.audit_event else []
        if not result.allowed:
            return ToolExecution(request=request, authorization=result, events=tuple(events))

        try:
            payload = executor(request)
            output = validate_tool_output(request.tool, payload)
        except Exception as error:  # a failing tool is audited, then reported as a failure
            message = f"{type(error).__name__}: {error}"
            failed = self._audit_execution(
                request, result, AuditResult.FAILED, after=None, error=message
            )
            if failed is not None:
                events.append(failed)
            return ToolExecution(
                request=request,
                authorization=result,
                error=message,
                events=tuple(events),
            )

        executed = self._audit_execution(
            request,
            result,
            AuditResult.SUCCEEDED,
            after={"output_digest": output.digest, "item_count": output.item_count},
            error=None,
        )
        if executed is not None:
            events.append(executed)
        return ToolExecution(
            request=request,
            authorization=result,
            output=output,
            events=tuple(events),
        )

    def _decide(self, request: ToolRequest) -> tuple[ToolDecision, tuple[str, ...]]:
        """Return the decision and its reasons for one request."""
        definition = self._catalogue.get(request.tool)
        if definition is None:
            return ToolDecision.DENY, (f"{request.tool.value} is not in the tool allowlist",)

        granted = self.permissions_for(request.agent_type)
        if definition.permission not in granted:
            return ToolDecision.DENY, (
                f"{request.agent_type.value} does not hold the {definition.permission.value} "
                f"permission required by {definition.tool.value}",
            )

        argument_reasons = validate_tool_arguments(definition, request.arguments)
        if argument_reasons:
            return ToolDecision.DENY, tuple(argument_reasons)

        if definition.kind is ToolKind.READ_ONLY:
            return ToolDecision.ALLOW, ()

        action_hash = request.action_hash
        if action_hash is None:
            return ToolDecision.DENY, (
                f"{definition.tool.value} changes state, so it must carry the "
                f"{ACTION_HASH_ARGUMENT} of the action it applies",
            )
        if not is_action_hash(action_hash):
            return ToolDecision.DENY, (f"{ACTION_HASH_ARGUMENT} must be a canonical sha256 hash",)

        if request.approval is not None and request.approval.decision is ApprovalDecision.REJECTED:
            return ToolDecision.DENY, ("the recorded approval was rejected",)

        if definition.kind is ToolKind.WRITE:
            return ToolDecision.ALLOW, (
                f"{definition.tool.value} only creates a reviewable artifact, "
                "which never changes production directly",
            )

        if request.environment is not Environment.PRODUCTION:
            return ToolDecision.ALLOW, (
                f"{definition.tool.value} runs in {request.environment.value}, "
                "where a mutation cannot reach production",
            )
        if request.approval is None:
            return ToolDecision.REQUIRE_APPROVAL, (
                "production mutation requires an explicit human approval bound to the action hash",
            )
        if not request.approval.is_usable(action_hash):
            return ToolDecision.REQUIRE_APPROVAL, (
                "the recorded approval does not authorise this action hash, "
                "was already consumed, or has expired",
            )
        return ToolDecision.ALLOW, ("approved production mutation",)

    def _correlation_id(self, request: ToolRequest, arguments_digest: str) -> str:
        """Return the correlation id for a tool event, deriving one when the request carries none."""
        return (
            request.correlation_id
            or request.incident_id
            or f"tool-{arguments_digest.removeprefix('sha256:')[:12]}"
        )

    def _audit_decision(
        self, request: ToolRequest, decision: ToolDecision, reasons: tuple[str, ...]
    ) -> AuditEvent | None:
        """Record the authorization decision for one tool call."""
        if self._trail is None:
            return None
        digest = tool_call_digest(request.tool, request.arguments)
        return self._trail.record_tool_invocation(
            actor=request.actor,
            tool=request.tool.value,
            arguments_digest=digest,
            decision=decision.value,
            result=DECISION_RESULTS[decision],
            correlation_id=self._correlation_id(request, digest),
            subject=request.incident_id,
            incident_id=request.incident_id,
            before={"target": request.target} if request.target else None,
            after={"decision": decision.value, "reasons": list(reasons)},
            error="; ".join(reasons) or None,
        )

    def _audit_execution(
        self,
        request: ToolRequest,
        result: AuthorizationResult,
        audit_result: AuditResult,
        *,
        after: Mapping[str, Any] | None,
        error: str | None,
    ) -> AuditEvent | None:
        """Record the execution result of one tool call."""
        if self._trail is None:
            return None
        return self._trail.record_tool_invocation(
            actor=request.actor,
            tool=request.tool.value,
            arguments_digest=result.arguments_digest,
            decision=result.decision.value,
            result=audit_result,
            correlation_id=self._correlation_id(request, result.arguments_digest),
            subject=request.incident_id,
            incident_id=request.incident_id,
            before={"target": request.target} if request.target else None,
            after=after,
            error=error,
        )
