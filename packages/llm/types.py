"""Value types and error taxonomy for the provider-agnostic LLM interface.

The interface in this package is deliberately narrow (ADR-0006): one request shape, one response shape,
one exception hierarchy. Providers translate their wire format into these types and nothing else in the
platform knows which provider is in use.

Two rules make the taxonomy useful:

* every failure mode an adapter can hit maps to exactly one exception, so retry and fallback policy is
  expressed as "retry these classes" instead of "inspect this message"; and
* a response always reports its own token usage, because the caller prices it, not the adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

MAX_CONTENT_LENGTH: Final[int] = 100_000
MAX_MESSAGES: Final[int] = 64


class LlmError(Exception):
    """Base class for every LLM interface failure."""


class LlmTimeoutError(LlmError):
    """The provider did not answer inside the deadline handed to it."""


class LlmUnavailableError(LlmError):
    """The provider is unreachable or returned a retryable server-side failure."""


class LlmRateLimitError(LlmError):
    """The provider refused the call because a rate limit was exceeded."""

    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class LlmRequestError(LlmError):
    """The request itself is invalid; retrying it would fail identically."""


class LlmBudgetExceededError(LlmError):
    """The configured token, cost, call or wall-clock budget would be exceeded."""


class LlmPricingError(LlmError):
    """No price is registered for a model, so cost could not be accounted."""


class LlmSchemaError(LlmError):
    """Model output could not be parsed into the requested schema."""


class Role(StrEnum):
    """Conversation roles the interface transports."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One bounded conversation message.

    Content is bounded because message text is attacker-influenceable (telemetry and GitHub content end up
    in prompts); an unbounded field would let one incident exhaust the prompt budget.
    """

    role: Role
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("message content must not be blank")
        if len(self.content) > MAX_CONTENT_LENGTH:
            raise ValueError(
                f"message content must not exceed {MAX_CONTENT_LENGTH} characters, "
                f"got {len(self.content)}"
            )

    def as_dict(self) -> dict[str, str]:
        """Return the provider-neutral ``{"role": ..., "content": ...}`` mapping."""
        return {"role": self.role.value, "content": self.content}


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Which model to call and how, including the per-call timeout."""

    provider: str
    model: str
    max_tokens: int = 4096
    temperature: float = 0.0
    top_p: float = 1.0
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must not be blank")
        if not self.model.strip():
            raise ValueError("model must not be blank")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be at least 1")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        if not 0.0 < self.top_p <= 1.0:
            raise ValueError("top_p must be greater than 0.0 and at most 1.0")
        if self.timeout_seconds <= 0.0:
            raise ValueError("timeout_seconds must be positive")

    @property
    def model_ref(self) -> str:
        """Return the ``provider/model`` reference recorded in the audit trail."""
        return f"{self.provider}/{self.model}"


@dataclass(frozen=True, slots=True)
class LlmRequest:
    """A single completion request, independent of provider wire format."""

    model_config: ModelConfig
    messages: tuple[ChatMessage, ...]

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("a request requires at least one message")
        if len(self.messages) > MAX_MESSAGES:
            raise ValueError(f"a request carries at most {MAX_MESSAGES} messages")

    def prompt_characters(self) -> int:
        """Return the total number of characters sent, used for prompt-token estimation."""
        return sum(len(message.content) for message in self.messages)


@dataclass(frozen=True, slots=True)
class Usage:
    """Token and cost accounting for one provider call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.prompt_tokens < 0 or self.completion_tokens < 0:
            raise ValueError("token counts must not be negative")
        if self.cost_usd < 0.0:
            raise ValueError("cost_usd must not be negative")

    @property
    def total_tokens(self) -> int:
        """Return prompt plus completion tokens."""
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: Usage) -> Usage:
        if not isinstance(other, Usage):
            return NotImplemented
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
        )


@dataclass(frozen=True, slots=True)
class LlmResponse:
    """A provider answer plus everything the audit trail needs to explain it."""

    content: str
    model_config: ModelConfig
    usage: Usage
    provider: str
    finish_reason: str | None = None
    attempts: int = 1
    latency_ms: int = 0

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("attempts must be at least 1")


__all__ = [
    "MAX_CONTENT_LENGTH",
    "MAX_MESSAGES",
    "ChatMessage",
    "LlmBudgetExceededError",
    "LlmError",
    "LlmPricingError",
    "LlmRateLimitError",
    "LlmRequest",
    "LlmRequestError",
    "LlmResponse",
    "LlmSchemaError",
    "LlmTimeoutError",
    "LlmUnavailableError",
    "ModelConfig",
    "Role",
    "Usage",
]
