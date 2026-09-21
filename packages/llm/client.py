"""The budgeted, retrying LLM client the control plane uses.

This is where the interface owns timeouts, retries, rate-limit handling, budgets and cost accounting
(ADR-0006). It wraps one provider or a :class:`~packages.llm.fallback.FallbackLlmProvider` chain:

* every attempt is bounded by ``min(run deadline, now + ModelConfig.timeout_seconds)``, and an adapter that
  overshoots is reported as a timeout — its reported usage is still recorded, because the tokens were spent;
* retryable failures repeat up to ``RetryPolicy.max_attempts`` with jittered exponential backoff, and a
  rate-limit ``retry_after`` is honoured, but no retry is ever scheduled past the run deadline;
* the attached :class:`~packages.llm.budget.UsageLedger` refuses a call that would breach the token, call,
  wall-clock or cost ceiling *before* it is made;
* an unpriced model fails before spending money rather than accounting a silent zero.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import logging
import random
import time

from packages.llm.budget import LlmBudget, UsageLedger
from packages.llm.fallback import FallbackLlmProvider
from packages.llm.pricing import PriceTable
from packages.llm.provider import LlmProvider
from packages.llm.retry import RetryPolicy
from packages.llm.types import (
    LlmError,
    LlmRateLimitError,
    LlmRequest,
    LlmResponse,
    LlmTimeoutError,
    Usage,
)

logger = logging.getLogger("llm.client")


class ResilientLlmProvider(LlmProvider):
    """Budget, timeout, retry and cost layer around a provider or a provider chain."""

    def __init__(
        self,
        provider: LlmProvider,
        *,
        budget: LlmBudget | None = None,
        ledger: UsageLedger | None = None,
        price_table: PriceTable | None = None,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        self._provider = provider
        self._ledger = ledger if ledger is not None else UsageLedger(budget or LlmBudget())
        self._price_table = price_table if price_table is not None else PriceTable()
        self._retry_policy = retry_policy if retry_policy is not None else RetryPolicy()
        self._sleep = sleep
        self._monotonic = monotonic
        self._random_value = random_value

    @property
    def name(self) -> str:
        """Return the wrapped provider name, marked as the resilient wrapper."""
        return f"resilient({self._provider.name})"

    @property
    def supported_models(self) -> tuple[str, ...]:
        """Return the wrapped provider's models."""
        return self._provider.supported_models

    @property
    def ledger(self) -> UsageLedger:
        """Return the accounting ledger for this run."""
        return self._ledger

    @property
    def usage(self) -> Usage:
        """Return what the run has spent so far."""
        return self._ledger.usage

    def remaining_cost_usd(self) -> float:
        """Return the unspent part of the run's cost ceiling."""
        return self._ledger.remaining_cost_usd

    def complete(self, request: LlmRequest, *, deadline: float) -> LlmResponse:
        """Return a priced completion, retrying retryable failures inside the budget."""
        self._ledger.check(request)
        price = self._price_table.price(request.model_config.model)
        run_deadline = min(deadline, self._ledger.deadline)
        attempts = 0

        while True:
            attempts += 1
            started = self._monotonic()
            attempt_deadline = min(run_deadline, started + request.model_config.timeout_seconds)
            try:
                response = self._provider.complete(request, deadline=attempt_deadline)
            except LlmError as error:
                self._raise_or_backoff(error, attempts=attempts, run_deadline=run_deadline)
                continue

            latency_ms = int((self._monotonic() - started) * 1000)
            completed = replace(
                response,
                usage=Usage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    cost_usd=price.cost_usd(
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                    ),
                ),
                attempts=attempts,
                latency_ms=latency_ms,
            )
            self._ledger.record(completed)
            if latency_ms > request.model_config.timeout_seconds * 1000:
                raise LlmTimeoutError(
                    f"provider {self._provider.name} answered after {latency_ms}ms, beyond the "
                    f"{request.model_config.timeout_seconds}s deadline"
                )
            return completed

    def _raise_or_backoff(self, error: LlmError, *, attempts: int, run_deadline: float) -> None:
        """Re-raise when no retry is possible, otherwise sleep before the next attempt."""
        if not RetryPolicy.is_retryable(error) or attempts >= self._retry_policy.max_attempts:
            raise error
        delay = self._retry_policy.backoff_seconds(attempts, random_value=self._random_value())
        if isinstance(error, LlmRateLimitError) and error.retry_after_seconds is not None:
            delay = max(delay, error.retry_after_seconds)
        if self._monotonic() + delay >= run_deadline:
            raise error
        logger.warning(
            "attempt %d/%d to %s failed with %s; retrying in %.3fs",
            attempts,
            self._retry_policy.max_attempts,
            self._provider.name,
            type(error).__name__,
            delay,
        )
        self._sleep(delay)


def build_llm_client(
    *providers: LlmProvider,
    budget: LlmBudget | None = None,
    ledger: UsageLedger | None = None,
    price_table: PriceTable | None = None,
    retry_policy: RetryPolicy | None = None,
) -> ResilientLlmProvider:
    """Return the platform's LLM client: the given providers in priority order, inside one budget.

    This is the single construction point for the control plane, so fallback order and budget policy are
    configured in one place instead of at every call site.
    """
    if not providers:
        raise ValueError("at least one provider is required")
    inner: LlmProvider = providers[0] if len(providers) == 1 else FallbackLlmProvider(providers)
    return ResilientLlmProvider(
        inner,
        budget=budget,
        ledger=ledger,
        price_table=price_table,
        retry_policy=retry_policy,
    )


__all__ = [
    "ResilientLlmProvider",
    "build_llm_client",
]
