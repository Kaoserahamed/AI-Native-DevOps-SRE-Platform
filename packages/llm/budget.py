"""Per-incident LLM budgets and usage accounting.

Budgets are enforced in code by the caller, never requested in the prompt (ADR-0006): the model cannot be
trusted to limit its own cost. One :class:`UsageLedger` covers one control-loop run (usually one incident)
and refuses a call that would breach any ceiling before the call is made.

Prompt sizes are *estimated* from characters because the interface has no tokenizer and a tokenizer per
provider would defeat the point of a provider-neutral layer. The estimate is deliberately conservative:
it over-counts rather than under-counts, so a budget breach is detected slightly early instead of late.
The exact counts a provider reports are what gets recorded and priced.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import math
import time
from typing import Final

from packages.llm.types import (
    LlmBudgetExceededError,
    LlmRequest,
    LlmResponse,
    Usage,
)

#: Average characters per token used for estimation. English prose and JSON both sit near this value.
CHARS_PER_TOKEN: Final[float] = 4.0


def estimate_tokens(text: str, *, chars_per_token: float = CHARS_PER_TOKEN) -> int:
    """Estimate the token count of ``text``, rounding up and never returning zero for non-empty text."""
    if chars_per_token <= 0.0:
        raise ValueError("chars_per_token must be positive")
    if not text:
        return 0
    return max(1, math.ceil(len(text) / chars_per_token))


@dataclass(frozen=True, slots=True)
class LlmBudget:
    """Ceilings for one control-loop run."""

    max_prompt_tokens: int = 100_000
    max_completion_tokens: int = 16_384
    max_cost_usd: float = 5.0
    max_calls: int = 8
    max_wall_clock_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.max_prompt_tokens < 1:
            raise ValueError("max_prompt_tokens must be at least 1")
        if self.max_completion_tokens < 1:
            raise ValueError("max_completion_tokens must be at least 1")
        if self.max_cost_usd < 0.0:
            raise ValueError("max_cost_usd must not be negative")
        if self.max_calls < 1:
            raise ValueError("max_calls must be at least 1")
        if self.max_wall_clock_seconds <= 0.0:
            raise ValueError("max_wall_clock_seconds must be positive")


@dataclass(slots=True)
class UsageLedger:
    """Mutable accounting for one run: what was spent, and what may still be spent."""

    budget: LlmBudget = field(default_factory=LlmBudget)
    clock: Callable[[], float] = time.monotonic
    usage: Usage = field(default_factory=Usage)
    calls: int = 0
    started_at: float = field(init=False)

    def __post_init__(self) -> None:
        self.started_at = self.clock()

    @property
    def deadline(self) -> float:
        """Return the absolute monotonic instant at which the run must stop calling the provider."""
        return self.started_at + self.budget.max_wall_clock_seconds

    @property
    def remaining_cost_usd(self) -> float:
        """Return the unspent part of the cost ceiling."""
        return max(0.0, self.budget.max_cost_usd - self.usage.cost_usd)

    def elapsed_seconds(self) -> float:
        """Return how long the run has been going, in seconds."""
        return self.clock() - self.started_at

    def projected_prompt_tokens(self, request: LlmRequest) -> int:
        """Return the prompt tokens this call would add to the run."""
        return self.usage.prompt_tokens + sum(
            estimate_tokens(message.content) for message in request.messages
        )

    def check(self, request: LlmRequest) -> None:
        """Raise :class:`LlmBudgetExceededError` when the next call may not be made."""
        if self.calls >= self.budget.max_calls:
            raise LlmBudgetExceededError(
                f"call budget exhausted: {self.calls} of {self.budget.max_calls} calls used"
            )
        remaining = self.deadline - self.clock()
        if remaining <= 0.0:
            raise LlmBudgetExceededError(
                f"wall-clock budget exhausted: {self.elapsed_seconds():.3f}s of "
                f"{self.budget.max_wall_clock_seconds}s used"
            )
        if request.model_config.max_tokens > self.budget.max_completion_tokens:
            raise LlmBudgetExceededError(
                f"requested max_tokens {request.model_config.max_tokens} exceeds the completion "
                f"budget {self.budget.max_completion_tokens}"
            )
        projected = self.projected_prompt_tokens(request)
        if projected > self.budget.max_prompt_tokens:
            raise LlmBudgetExceededError(
                f"prompt budget exceeded: about {projected} tokens against a ceiling of "
                f"{self.budget.max_prompt_tokens}"
            )

    def record(self, response: LlmResponse) -> Usage:
        """Add a completed call to the running totals and return the new totals."""
        self.usage = self.usage + response.usage
        self.calls += 1
        return self.usage


__all__ = [
    "CHARS_PER_TOKEN",
    "LlmBudget",
    "UsageLedger",
    "estimate_tokens",
]
