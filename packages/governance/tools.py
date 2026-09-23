"""Agent tool catalogue: allowlist, argument limits and structured output validation (Task 12.3).

An agent can only reach the outside world through a tool declared here. The catalogue is explicit about three
things the authorization layer then enforces:

* **Which capability a tool needs.** Every tool requires exactly one :class:`ToolPermission`, so a per-agent
  permission set is a small, reviewable list rather than an implicit "can do anything".
* **Which arguments are acceptable.** A tool declares the argument names it accepts, how many it accepts, and
  how long a value may be. An unexpected argument is refused before the tool runs, because an unbounded
  argument map is both a prompt-injection payload and an unbounded API call.
* **What a valid answer looks like.** Tool output is untrusted input like any other telemetry: it is validated
  against a bounded envelope (:class:`ToolOutput`) and rejected when it names a different tool or exceeds the
  size limits, so a malformed or over-sized answer never reaches a prompt or a decision.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Annotated, Any, Final, Self

from pydantic import Field, StringConstraints, ValidationError, computed_field, model_validator

from packages.contracts.common import (
    MAX_MAPPING_VALUE_LENGTH,
    Labels,
    ShortText,
    UtcDatetime,
    ValueModel,
    sha256_digest,
)

MAX_TOOL_ARGUMENTS: Final[int] = 8
MAX_TOOL_ARGUMENT_LENGTH: Final[int] = 512
MAX_TOOL_OUTPUT_ITEMS: Final[int] = 100
MAX_TOOL_ITEM_ATTRIBUTES: Final[int] = 16

#: Argument every state-changing tool must carry: the hash of the action it acts on.
ACTION_HASH_ARGUMENT: Final[str] = "action_hash"

ACTION_HASH_PATTERN: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")
ToolItemKind = Annotated[str, StringConstraints(min_length=1, max_length=64)]


def is_action_hash(value: object) -> bool:
    """Return whether ``value`` is a canonical (``sha256:``) action hash."""
    return isinstance(value, str) and bool(ACTION_HASH_PATTERN.match(value))


class ToolPermission(StrEnum):
    """Capabilities an agent may hold. A tool requires exactly one of them."""

    READ_TELEMETRY = "read_telemetry"
    READ_DEPLOYMENT_HISTORY = "read_deployment_history"
    WRITE_ISSUE = "write_issue"
    WRITE_PULL_REQUEST = "write_pull_request"
    MUTATE_WORKLOAD = "mutate_workload"


class ToolKind(StrEnum):
    """How far a tool reaches; drives whether approval is required."""

    READ_ONLY = "read_only"
    WRITE = "write"
    MUTATING = "mutating"


class AgentTool(StrEnum):
    """Every tool an agent may invoke."""

    LOG_QUERY = "log_query"
    PROMETHEUS_QUERY = "prometheus_query"
    TRACE_QUERY = "trace_query"
    KUBERNETES_INSPECT = "kubernetes_inspect"
    DEPLOYMENT_HISTORY = "deployment_history"
    REPOSITORY_READ = "repository_read"
    ISSUE_CREATE = "issue_create"
    PULL_REQUEST_CREATE = "pull_request_create"
    WORKLOAD_RESTART = "workload_restart"
    WORKLOAD_ROLLBACK = "workload_rollback"


class ToolOutputValidationError(ValueError):
    """Raised when a tool returns something other than the envelope it promises."""


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """One declared tool: what it needs, what it accepts and what it may return."""

    tool: AgentTool
    kind: ToolKind
    permission: ToolPermission
    description: str
    allowed_arguments: frozenset[str]
    max_arguments: int = MAX_TOOL_ARGUMENTS
    max_argument_length: int = MAX_TOOL_ARGUMENT_LENGTH

    def __post_init__(self) -> None:
        """Reject a definition that does not describe a usable tool."""
        if not self.description.strip():
            raise ValueError(f"{self.tool.value} needs a description")
        if len(self.allowed_arguments) > self.max_arguments:
            raise ValueError(
                f"{self.tool.value} declares {len(self.allowed_arguments)} arguments but allows "
                f"at most {self.max_arguments}"
            )
        if (
            self.kind is not ToolKind.READ_ONLY
            and ACTION_HASH_ARGUMENT not in self.allowed_arguments
        ):
            raise ValueError(
                f"{self.tool.value} changes state, so it must accept the {ACTION_HASH_ARGUMENT} "
                "argument that binds the call to an approved action"
            )


#: Arguments a read-only telemetry query may carry. Each family declares only the arguments it can act
#: on, so the allowlist stays a superset of nothing: ``MAX_TOOL_ARGUMENTS`` bounds every tool, and a tool
#: that accepted an argument it cannot use would turn an argument-map into an unbounded API call.
LOG_ARGUMENTS: Final[frozenset[str]] = frozenset(
    {"service", "namespace", "workload", "query", "start", "end", "limit"}
)

#: Arguments a bounded PromQL query may carry. It is keyed by query text rather than a workload name.
METRIC_ARGUMENTS: Final[frozenset[str]] = frozenset(
    {"service", "namespace", "query", "start", "end", "limit"}
)

#: Arguments a trace sample may carry; ``revision`` narrows a sample to one release.
TRACE_ARGUMENTS: Final[frozenset[str]] = frozenset(
    {"service", "namespace", "workload", "query", "start", "end", "limit", "revision"}
)

#: Arguments a workload inspection may carry.
INSPECT_ARGUMENTS: Final[frozenset[str]] = frozenset(
    {"service", "namespace", "workload", "kind", "limit"}
)

#: Arguments a deployment-history read may carry.
DEPLOYMENT_ARGUMENTS: Final[frozenset[str]] = frozenset(
    {"service", "namespace", "workload", "kind", "limit", "revision"}
)

TOOL_DEFINITIONS: Final[Mapping[AgentTool, ToolDefinition]] = {
    AgentTool.LOG_QUERY: ToolDefinition(
        tool=AgentTool.LOG_QUERY,
        kind=ToolKind.READ_ONLY,
        permission=ToolPermission.READ_TELEMETRY,
        description="Query the log backend for a service and time window.",
        allowed_arguments=LOG_ARGUMENTS,
    ),
    AgentTool.PROMETHEUS_QUERY: ToolDefinition(
        tool=AgentTool.PROMETHEUS_QUERY,
        kind=ToolKind.READ_ONLY,
        permission=ToolPermission.READ_TELEMETRY,
        description="Run a bounded PromQL query over the evidence window.",
        allowed_arguments=METRIC_ARGUMENTS,
    ),
    AgentTool.TRACE_QUERY: ToolDefinition(
        tool=AgentTool.TRACE_QUERY,
        kind=ToolKind.READ_ONLY,
        permission=ToolPermission.READ_TELEMETRY,
        description="Sample traces for a service inside the evidence window.",
        allowed_arguments=TRACE_ARGUMENTS,
    ),
    AgentTool.KUBERNETES_INSPECT: ToolDefinition(
        tool=AgentTool.KUBERNETES_INSPECT,
        kind=ToolKind.READ_ONLY,
        permission=ToolPermission.READ_TELEMETRY,
        description="Read workload status, conditions and recent events.",
        allowed_arguments=INSPECT_ARGUMENTS,
    ),
    AgentTool.DEPLOYMENT_HISTORY: ToolDefinition(
        tool=AgentTool.DEPLOYMENT_HISTORY,
        kind=ToolKind.READ_ONLY,
        permission=ToolPermission.READ_DEPLOYMENT_HISTORY,
        description="Read deployment and release history for a service.",
        allowed_arguments=DEPLOYMENT_ARGUMENTS,
    ),
    AgentTool.REPOSITORY_READ: ToolDefinition(
        tool=AgentTool.REPOSITORY_READ,
        kind=ToolKind.READ_ONLY,
        permission=ToolPermission.READ_DEPLOYMENT_HISTORY,
        description="Read repository metadata, commits and configuration diffs.",
        allowed_arguments=frozenset({"repository", "path", "ref", "limit"}),
    ),
    AgentTool.ISSUE_CREATE: ToolDefinition(
        tool=AgentTool.ISSUE_CREATE,
        kind=ToolKind.WRITE,
        permission=ToolPermission.WRITE_ISSUE,
        description="Open an evidence-backed incident issue.",
        # A write reaches outside the platform, so the authorizer requires the action hash that binds the
        # issue to the decision that produced it. The definition must therefore accept that argument.
        allowed_arguments=frozenset(
            {"repository", "title", "body", "incident_id", ACTION_HASH_ARGUMENT}
        ),
    ),
    AgentTool.PULL_REQUEST_CREATE: ToolDefinition(
        tool=AgentTool.PULL_REQUEST_CREATE,
        kind=ToolKind.WRITE,
        permission=ToolPermission.WRITE_PULL_REQUEST,
        description="Open a remediation pull request for an approved proposal.",
        allowed_arguments=frozenset(
            {"repository", "branch", "base", "title", "body", ACTION_HASH_ARGUMENT}
        ),
    ),
    AgentTool.WORKLOAD_RESTART: ToolDefinition(
        tool=AgentTool.WORKLOAD_RESTART,
        kind=ToolKind.MUTATING,
        permission=ToolPermission.MUTATE_WORKLOAD,
        description="Restart a workload after an approved remediation.",
        allowed_arguments=frozenset(
            {"namespace", "workload", "kind", ACTION_HASH_ARGUMENT, "approval_id"}
        ),
    ),
    AgentTool.WORKLOAD_ROLLBACK: ToolDefinition(
        tool=AgentTool.WORKLOAD_ROLLBACK,
        kind=ToolKind.MUTATING,
        permission=ToolPermission.MUTATE_WORKLOAD,
        description="Roll a workload back to a previous revision after an approved remediation.",
        allowed_arguments=frozenset(
            {"namespace", "workload", "kind", "revision", ACTION_HASH_ARGUMENT, "approval_id"}
        ),
    ),
}


class ToolOutputItem(ValueModel):
    """One bounded item of a tool answer."""

    kind: ToolItemKind
    summary: ShortText
    observed_at: UtcDatetime | None = None
    attributes: Labels = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        """Bound the attribute map so one answer cannot flood a prompt."""
        if len(self.attributes) > MAX_TOOL_ITEM_ATTRIBUTES:
            raise ValueError(
                f"at most {MAX_TOOL_ITEM_ATTRIBUTES} attributes are allowed per tool output item"
            )
        for value in self.attributes.values():
            if len(value) > MAX_MAPPING_VALUE_LENGTH:
                raise ValueError(
                    f"a tool output attribute must not exceed {MAX_MAPPING_VALUE_LENGTH} characters"
                )
        return self


class ToolOutput(ValueModel):
    """The envelope every tool answer must conform to."""

    tool: AgentTool
    items: list[ToolOutputItem] = Field(default_factory=list, max_length=MAX_TOOL_OUTPUT_ITEMS)
    truncated: bool = False

    @computed_field(  # type: ignore[prop-decorator]
        description="Digest of the answer, used to reference it from an evidence record."
    )
    @property
    def digest(self) -> str:
        """Return the sha256 digest of the answer's content."""
        return sha256_digest(
            {
                "tool": self.tool.value,
                "items": [item.model_dump(mode="json") for item in self.items],
                "truncated": self.truncated,
            }
        )

    @property
    def item_count(self) -> int:
        """Return how many items the answer carries."""
        return len(self.items)


def validate_tool_output(tool: AgentTool, payload: Mapping[str, Any]) -> ToolOutput:
    """Validate a structured tool answer against the envelope the tool promises.

    Parameters
    ----------
    tool
        The tool that produced the answer.
    payload
        Raw answer, normally decoded JSON.

    Raises
    ------
    ToolOutputValidationError
        When the answer is not the envelope, names another tool, or exceeds the bounds.
    """
    try:
        output = ToolOutput.model_validate(dict(payload))
    except ValidationError as error:
        raise ToolOutputValidationError(
            f"{tool.value} returned an invalid payload: {error.error_count()} problem(s)"
        ) from error
    if output.tool is not tool:
        raise ToolOutputValidationError(
            f"{tool.value} returned a payload that claims to come from {output.tool.value}"
        )
    return output


def validate_tool_arguments(
    definition: ToolDefinition, arguments: Mapping[str, object]
) -> list[str]:
    """Return the reasons ``arguments`` must not reach the tool; empty when acceptable."""
    reasons: list[str] = []
    if len(arguments) > definition.max_arguments:
        reasons.append(
            f"{definition.tool.value} accepts at most {definition.max_arguments} arguments, "
            f"got {len(arguments)}"
        )
    for name, value in arguments.items():
        if name not in definition.allowed_arguments:
            reasons.append(f"argument {name!r} is not allowed for {definition.tool.value}")
            continue
        if isinstance(value, bool | int | float):
            continue
        if not isinstance(value, str):
            reasons.append(f"argument {name!r} must be a string, number or boolean")
            continue
        if not value:
            reasons.append(f"argument {name!r} must not be empty")
        elif len(value) > definition.max_argument_length:
            reasons.append(
                f"argument {name!r} must not exceed {definition.max_argument_length} characters"
            )
    return reasons


def tool_call_digest(tool: AgentTool, arguments: Mapping[str, object]) -> str:
    """Return the sha256 digest of a tool call, used as the audit and idempotency reference."""
    ordered = {name: str(arguments[name]) for name in sorted(arguments)}
    return sha256_digest({"tool": tool.value, "arguments": ordered})
