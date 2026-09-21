"""Provider-agnostic LLM interface.

Supports multiple providers with a common interface, timeout handling,
retry policy, rate-limit handling, token/cost accounting, and structured output.

(Phase 8.1 — LLM abstraction.)
"""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for a specific model."""
    provider: str
    model: str
    max_tokens: int = 4096
    temperature: float = 0.0
    top_p: float = 1.0


@dataclass
class Usage:
    """Token and cost accounting for one LLM call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class LlmRequest:
    """A single LLM completion request."""
    messages: list[dict[str, str]]
    model_config: ModelConfig
    schema: type[BaseModel] | None = None


@dataclass
class LlmResponse:
    """A single LLM completion response."""
    content: str
    usage: Usage = field(default_factory=Usage)
    raw_response: dict[str, Any] = field(default_factory=dict)


class LlmError(Exception):
    """Base exception for LLM provider errors."""


class LlmTimeoutError(LlmError):
    """The LLM call timed out."""


class LlmRateLimitError(LlmError):
    """The LLM provider returned a rate-limit error."""


class LlmProviderError(LlmError):
    """A non-retryable error from the LLM provider."""


class LlmProvider(ABC):
    """Abstract base for LLM providers.

    Implementations must be thread-safe and idempotent for identical requests.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """The provider identifier, e.g. 'openai', 'anthropic'."""

    @property
    @abstractmethod
    def supported_models(self) -> list[str]:
        """Models this provider can serve."""

    @abstractmethod
    def complete(
        self,
        request: LlmRequest,
        *,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> LlmResponse:
        """Complete a prompt, with bounded retries and timeout."""


class TokenBudgetExceeded(LlmError):
    """Raised when a request would exceed the configured token budget."""


@dataclass
class TokenBudget:
    """Per-incident token budget."""
    max_prompt_tokens: int = 100_000
    max_completion_tokens: int = 20_000
    max_cost_usd: float = 5.0

    def __post_init__(self) -> None:
        if self.max_prompt_tokens <= 0:
            raise ValueError("max_prompt_tokens must be positive")
        if self.max_completion_tokens <= 0:
            raise ValueError("max_completion_tokens must be positive")
        if self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be non-negative")

    def check(self, request: LlmRequest, existing_usage: Usage) -> None:
        """Raise TokenBudgetExceeded if the request exceeds the budget."""
        projected_prompt = existing_usage.prompt_tokens + sum(
            len(m.get("content", "")) for m in request.messages
        )
        if projected_prompt > self.max_prompt_tokens:
            raise TokenBudgetExceeded(
                f"prompt tokens {projected_prompt} exceed budget {self.max_prompt_tokens}"
            )
        if request.model_config.max_tokens > self.max_completion_tokens:
            raise TokenBudgetExceeded(
                f"request max_tokens {request.model_config.max_tokens} "
                f"exceeds budget {self.max_completion_tokens}"
            )


class FakeLlmProvider(LlmProvider):
    """A deterministic fake provider for unit tests.

    Returns pre-configured responses based on the request content hash,
    so tests can predict behavior without a real LLM.
    """

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._responses: dict[str, str] = responses or {}

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def supported_models(self) -> list[str]:
        return ["fake-model"]

    def complete(
        self,
        request: LlmRequest,
        *,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> LlmResponse:
        # Hash the messages to pick a deterministic response
        key = hashlib.sha256(
            json.dumps(request.messages, sort_keys=True).encode()
        ).hexdigest()[:16]
        default = '{"diagnosis": "unknown", "confidence": 0.0, "summary": "No analysis available"}'
        content = self._responses.get(key, default)
        return LlmResponse(
            content=content,
            usage=Usage(prompt_tokens=100, completion_tokens=50, cost_usd=0.001),
            raw_response={"model": "fake-model", "key": key},
        )


__all__ = [
    "LlmError",
    "LlmProvider",
    "LlmRequest",
    "LlmResponse",
    "LlmRateLimitError",
    "LlmTimeoutError",
    "LlmProviderError",
    "ModelConfig",
    "TokenBudget",
    "TokenBudgetExceeded",
    "Usage",
    "FakeLlmProvider",
]