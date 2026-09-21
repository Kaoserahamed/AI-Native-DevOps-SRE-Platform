"""Retry and backoff policy for provider calls.

Keeping the policy in its own module means the delay maths is unit-testable without a provider, and both the
fallback chain and the resilient client reason about the same definition of "retryable".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from packages.llm.types import (
    LlmError,
    LlmRateLimitError,
    LlmTimeoutError,
    LlmUnavailableError,
)

#: Failures a retry (possibly on another provider) may resolve. Everything else — an invalid request, a
#: pricing gap, a budget breach, a schema violation — is deterministic and is raised to the caller.
RETRYABLE_ERRORS: Final[tuple[type[LlmError], ...]] = (
    LlmTimeoutError,
    LlmRateLimitError,
    LlmUnavailableError,
)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """How often and how long to wait before repeating a failed attempt."""

    max_attempts: int = 3
    initial_backoff_seconds: float = 0.5
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 8.0
    jitter_ratio: float = 0.2

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_backoff_seconds < 0.0:
            raise ValueError("initial_backoff_seconds must not be negative")
        if self.backoff_multiplier < 1.0:
            raise ValueError("backoff_multiplier must be at least 1.0")
        if self.max_backoff_seconds < self.initial_backoff_seconds:
            raise ValueError("max_backoff_seconds must not be smaller than initial_backoff_seconds")
        if not 0.0 <= self.jitter_ratio < 1.0:
            raise ValueError("jitter_ratio must be in [0.0, 1.0)")

    def backoff_seconds(self, attempt: int, *, random_value: float) -> float:
        """Return the delay before retrying after the 1-based ``attempt`` failed.

        The delay is exponential and capped, then spread over ``[base * (1 - jitter), base * (1 + jitter))``
        so that many workers failing against one provider do not retry in lockstep.
        """
        if attempt < 1:
            raise ValueError("attempt must be at least 1")
        base = min(
            self.max_backoff_seconds,
            self.initial_backoff_seconds * self.backoff_multiplier ** (attempt - 1),
        )
        if self.jitter_ratio == 0.0:
            return base
        bounded = min(max(random_value, 0.0), 1.0)
        return base * (1.0 - self.jitter_ratio + 2.0 * self.jitter_ratio * bounded)

    @staticmethod
    def is_retryable(error: BaseException) -> bool:
        """Return whether ``error`` is one a retry could resolve."""
        return isinstance(error, RETRYABLE_ERRORS)


__all__ = [
    "RETRYABLE_ERRORS",
    "RetryPolicy",
]
