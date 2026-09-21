"""Provider-agnostic LLM interface (ADR-0006, `docs/08-ai-agents.md`).

One narrow interface — :meth:`~packages.llm.provider.LlmProvider.complete` and
:meth:`~packages.llm.provider.LlmProvider.complete_structured` — with every cross-cutting concern owned by
the interface instead of by the agents that call it:

* :mod:`packages.llm.types` — request, response, usage and the error taxonomy,
* :mod:`packages.llm.pricing` — model prices and cost accounting,
* :mod:`packages.llm.budget` — per-run token, call, wall-clock and cost ceilings,
* :mod:`packages.llm.retry` — retryability and jittered exponential backoff,
* :mod:`packages.llm.fallback` — provider fallback policy,
* :mod:`packages.llm.client` — the budgeted client the control plane uses,
* :mod:`packages.llm.structured` — schema-validated output parsing,
* :mod:`packages.llm.fake` — the deterministic provider used by every test tier.

Provider adapters (OpenAI-compatible, Anthropic-style, local runtime) implement
:class:`~packages.llm.provider.LlmProvider` and add no policy of their own.
"""

from __future__ import annotations

from packages.llm.budget import LlmBudget, UsageLedger, estimate_tokens
from packages.llm.client import ResilientLlmProvider, build_llm_client
from packages.llm.fake import DEFAULT_CONTENT, FakeLlmProvider, ScriptedReply, fingerprint
from packages.llm.fallback import FallbackLlmProvider
from packages.llm.pricing import DEFAULT_PRICES, ModelPrice, PriceTable
from packages.llm.provider import LlmProvider
from packages.llm.retry import RETRYABLE_ERRORS, RetryPolicy
from packages.llm.structured import parse_structured
from packages.llm.types import (
    MAX_CONTENT_LENGTH,
    MAX_MESSAGES,
    ChatMessage,
    LlmBudgetExceededError,
    LlmError,
    LlmPricingError,
    LlmRateLimitError,
    LlmRequest,
    LlmRequestError,
    LlmResponse,
    LlmSchemaError,
    LlmTimeoutError,
    LlmUnavailableError,
    ModelConfig,
    Role,
    Usage,
)

__all__ = [
    "DEFAULT_CONTENT",
    "DEFAULT_PRICES",
    "MAX_CONTENT_LENGTH",
    "MAX_MESSAGES",
    "RETRYABLE_ERRORS",
    "ChatMessage",
    "FakeLlmProvider",
    "FallbackLlmProvider",
    "LlmBudget",
    "LlmBudgetExceededError",
    "LlmError",
    "LlmPricingError",
    "LlmProvider",
    "LlmRateLimitError",
    "LlmRequest",
    "LlmRequestError",
    "LlmResponse",
    "LlmSchemaError",
    "LlmTimeoutError",
    "LlmUnavailableError",
    "ModelConfig",
    "ModelPrice",
    "PriceTable",
    "ResilientLlmProvider",
    "RetryPolicy",
    "Role",
    "ScriptedReply",
    "Usage",
    "UsageLedger",
    "build_llm_client",
    "estimate_tokens",
    "fingerprint",
    "parse_structured",
]
