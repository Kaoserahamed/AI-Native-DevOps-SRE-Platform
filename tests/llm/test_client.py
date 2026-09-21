"""Tests for the budgeted, retrying LLM client.

These are the tests that make the interface's promises executable: a completed call is priced from the
reported tokens, retryable failures back off and repeat, a rate limit's own delay is honoured, an invalid
request is never retried, budgets are checked before spending, and an adapter that ignores its deadline is
reported as a timeout.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

import pytest

from packages.llm import (
    FakeLlmProvider,
    LlmBudget,
    LlmBudgetExceededError,
    LlmPricingError,
    LlmProvider,
    LlmRateLimitError,
    LlmRequest,
    LlmRequestError,
    LlmResponse,
    LlmTimeoutError,
    LlmUnavailableError,
    ModelConfig,
    PriceTable,
    ResilientLlmProvider,
    RetryPolicy,
    ScriptedReply,
    Usage,
    UsageLedger,
    build_llm_client,
)
from packages.test_fixtures.clock import FakeClock, SleepRecorder

pytestmark = pytest.mark.unit

PRICED_MODEL: Final[str] = "gpt-4o-mini"
# (1000 * 0.15 + 1000 * 0.60) / 1_000_000
EXPECTED_COST_USD: Final[float] = 0.00075


def _config(model: str = PRICED_MODEL, *, timeout_seconds: float = 5.0) -> ModelConfig:
    """Return a model configuration in the priced default table."""
    return ModelConfig(
        provider="fake", model=model, max_tokens=256, timeout_seconds=timeout_seconds
    )


def _client(
    provider: LlmProvider,
    clock: FakeClock,
    sleep: SleepRecorder,
    *,
    budget: LlmBudget | None = None,
    retry_policy: RetryPolicy | None = None,
    price_table: PriceTable | None = None,
) -> ResilientLlmProvider:
    """Return a client driven by the fake clock and the delay recorder."""
    return ResilientLlmProvider(
        provider,
        budget=budget,
        price_table=price_table,
        retry_policy=retry_policy,
        monotonic=clock,
        sleep=sleep,
        random_value=lambda: 0.5,
    )


def test_completed_call_is_priced_and_recorded(
    clock: FakeClock, sleep_recorder: SleepRecorder, build_request: Callable[..., LlmRequest]
) -> None:
    """Cost comes from the reported tokens and the committed price table, per call."""
    provider = FakeLlmProvider(
        model=PRICED_MODEL,
        script=[
            ScriptedReply(
                content="diagnosis", usage=Usage(prompt_tokens=1_000, completion_tokens=1_000)
            )
        ],
    )
    client = _client(provider, clock, sleep_recorder)
    request = build_request("diagnose INC-2026-0001", config=_config())

    response = client.complete(request, deadline=clock.deadline_in(30.0))

    assert response.provider == "fake"
    assert response.content == "diagnosis"
    assert response.attempts == 1
    assert response.latency_ms == 0
    assert response.usage.cost_usd == pytest.approx(EXPECTED_COST_USD)
    assert client.usage.prompt_tokens == 1_000
    assert client.usage.completion_tokens == 1_000
    assert client.usage.cost_usd == pytest.approx(EXPECTED_COST_USD)
    assert client.ledger.calls == 1
    assert client.remaining_cost_usd() == pytest.approx(5.0 - EXPECTED_COST_USD)

    assert client.name == "resilient(fake)"
    assert client.supported_models == (PRICED_MODEL,)


def test_rate_limit_is_retried_with_backoff(
    clock: FakeClock, sleep_recorder: SleepRecorder, build_request: Callable[..., LlmRequest]
) -> None:
    """A rate limit is transient: wait, then try again instead of failing the incident."""
    provider = FakeLlmProvider(
        model=PRICED_MODEL,
        script=[LlmRateLimitError("slow down"), ScriptedReply(content="recovered")],
    )
    client = _client(
        provider,
        clock,
        sleep_recorder,
        retry_policy=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.5, jitter_ratio=0.0),
    )

    response = client.complete(
        build_request("diagnose", config=_config()), deadline=clock.deadline_in(30.0)
    )

    assert response.content == "recovered"
    assert response.attempts == 2
    assert sleep_recorder.delays == [pytest.approx(0.5)]
    assert len(provider.calls) == 2


def test_rate_limit_own_delay_is_honoured(
    clock: FakeClock, sleep_recorder: SleepRecorder, build_request: Callable[..., LlmRequest]
) -> None:
    """A provider that says "come back in 3 seconds" is believed rather than hammered."""
    provider = FakeLlmProvider(
        model=PRICED_MODEL,
        script=[LlmRateLimitError("busy", retry_after_seconds=3.0), ScriptedReply(content="ok")],
    )
    client = _client(provider, clock, sleep_recorder)

    client.complete(build_request("diagnose", config=_config()), deadline=clock.deadline_in(30.0))

    assert sleep_recorder.delays == [pytest.approx(3.0)]


def test_attempts_stop_at_the_policy_limit(
    clock: FakeClock, sleep_recorder: SleepRecorder, build_request: Callable[..., LlmRequest]
) -> None:
    """Bounded retries keep one stuck provider from consuming the run's wall-clock budget."""
    provider = FakeLlmProvider(
        model=PRICED_MODEL,
        script=[LlmRateLimitError("busy"), LlmRateLimitError("busy"), ScriptedReply(content="ok")],
    )
    client = _client(
        provider,
        clock,
        sleep_recorder,
        retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.5, jitter_ratio=0.0),
    )

    with pytest.raises(LlmRateLimitError):
        client.complete(
            build_request("diagnose", config=_config()), deadline=clock.deadline_in(30.0)
        )

    assert len(provider.calls) == 2
    assert provider.remaining_script == 1


def test_retry_is_not_scheduled_past_the_deadline(
    clock: FakeClock, sleep_recorder: SleepRecorder, build_request: Callable[..., LlmRequest]
) -> None:
    """A retry that cannot fit inside the deadline fails now instead of overrunning the run."""
    provider = FakeLlmProvider(
        model=PRICED_MODEL,
        script=[LlmRateLimitError("busy", retry_after_seconds=10.0), ScriptedReply(content="ok")],
    )
    client = _client(provider, clock, sleep_recorder)

    with pytest.raises(LlmRateLimitError):
        client.complete(
            build_request("diagnose", config=_config()), deadline=clock.deadline_in(1.0)
        )

    assert sleep_recorder.delays == []


def test_invalid_request_is_not_retried(
    clock: FakeClock, sleep_recorder: SleepRecorder, build_request: Callable[..., LlmRequest]
) -> None:
    """Retrying a rejected request would only waste the run's budget."""
    provider = FakeLlmProvider(model=PRICED_MODEL, script=[LlmRequestError("malformed")])
    client = _client(provider, clock, sleep_recorder)

    with pytest.raises(LlmRequestError):
        client.complete(
            build_request("diagnose", config=_config()), deadline=clock.deadline_in(30.0)
        )

    assert len(provider.calls) == 1
    assert sleep_recorder.delays == []


def test_call_budget_is_checked_before_the_provider_is_asked(
    clock: FakeClock, sleep_recorder: SleepRecorder, build_request: Callable[..., LlmRequest]
) -> None:
    """The ceiling stops a runaway loop before it spends anything."""
    provider = FakeLlmProvider(model=PRICED_MODEL, script=[ScriptedReply(content="first")])
    client = _client(provider, clock, sleep_recorder, budget=LlmBudget(max_calls=1))
    request = build_request("diagnose", config=_config())

    client.complete(request, deadline=clock.deadline_in(30.0))
    with pytest.raises(LlmBudgetExceededError, match="call budget exhausted"):
        client.complete(request, deadline=clock.deadline_in(30.0))

    assert len(provider.calls) == 1


def test_prompt_budget_is_checked_before_the_provider_is_asked(
    clock: FakeClock, sleep_recorder: SleepRecorder, build_request: Callable[..., LlmRequest]
) -> None:
    """A prompt that would breach the token ceiling never leaves the process."""
    provider = FakeLlmProvider(model=PRICED_MODEL, script=[ScriptedReply(content="ok")])
    client = _client(provider, clock, sleep_recorder, budget=LlmBudget(max_prompt_tokens=50))

    with pytest.raises(LlmBudgetExceededError, match="prompt budget exceeded"):
        client.complete(
            build_request("x" * 400, config=_config()), deadline=clock.deadline_in(30.0)
        )

    assert provider.calls == ()


def test_unpriced_model_fails_before_spending(
    clock: FakeClock, sleep_recorder: SleepRecorder, build_request: Callable[..., LlmRequest]
) -> None:
    """An unpriced model would disable the cost ceiling, so it is refused up front."""
    provider = FakeLlmProvider(model="mystery-model", script=[ScriptedReply(content="ok")])
    client = _client(provider, clock, sleep_recorder)

    with pytest.raises(LlmPricingError, match="no price registered"):
        client.complete(
            build_request("diagnose", config=_config("mystery-model")),
            deadline=clock.deadline_in(30.0),
        )

    assert provider.calls == ()


def test_fallback_chain_serves_the_call_and_is_priced(
    clock: FakeClock, build_request: Callable[..., LlmRequest]
) -> None:
    """The client wraps the whole chain, so a provider incident is invisible to the caller."""
    primary = FakeLlmProvider(
        provider="primary", model=PRICED_MODEL, script=[LlmUnavailableError("outage")]
    )
    secondary = FakeLlmProvider(
        provider="secondary",
        model=PRICED_MODEL,
        script=[
            ScriptedReply(
                content="from the fallback", usage=Usage(prompt_tokens=10, completion_tokens=10)
            )
        ],
    )
    client = build_llm_client(
        primary,
        secondary,
        ledger=UsageLedger(clock=clock),
        price_table=PriceTable(),
        retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.0, jitter_ratio=0.0),
    )

    response = client.complete(
        build_request("diagnose", config=_config()), deadline=clock.deadline_in(30.0)
    )

    assert response.provider == "secondary"
    # Walking the chain is one attempt: the fallback hides the primary's failure from the caller.
    assert response.attempts == 1
    assert response.usage.cost_usd == pytest.approx((10 * 0.15 + 10 * 0.60) / 1_000_000)
    assert client.name == "resilient(fallback[primary->secondary])"
    assert len(primary.calls) == 1
    assert len(secondary.calls) == 1


class DeadlineIgnoringProvider(LlmProvider):
    """An adapter that breaks the contract by answering later than its deadline allows."""

    def __init__(self, clock: FakeClock, latency_seconds: float) -> None:
        self._clock = clock
        self._latency_seconds = latency_seconds

    @property
    def name(self) -> str:
        """Return the adapter name."""
        return "deadline-ignoring"

    @property
    def supported_models(self) -> tuple[str, ...]:
        """Return the model this adapter claims to serve."""
        return (PRICED_MODEL,)

    def complete(self, request: LlmRequest, *, deadline: float) -> LlmResponse:
        """Spend more time than the deadline allows, then answer anyway."""
        self._clock.advance(self._latency_seconds)
        return LlmResponse(
            content="late answer",
            model_config=request.model_config,
            usage=Usage(prompt_tokens=10, completion_tokens=2),
            provider="deadline-ignoring",
        )


def test_adapter_that_ignores_its_deadline_is_reported_as_a_timeout(
    clock: FakeClock, sleep_recorder: SleepRecorder, build_request: Callable[..., LlmRequest]
) -> None:
    """The interface owns the timeout: an overshooting adapter cannot silently stall the run."""
    client = _client(DeadlineIgnoringProvider(clock, 5.0), clock, sleep_recorder)

    with pytest.raises(LlmTimeoutError, match=r"beyond the 1\.0s deadline"):
        client.complete(
            build_request("diagnose", config=_config(timeout_seconds=1.0)),
            deadline=clock.deadline_in(30.0),
        )

    # The tokens were really spent, so the run's accounting still reflects them.
    assert client.usage.prompt_tokens == 10


def test_client_requires_at_least_one_provider() -> None:
    """A client without a provider could never produce a diagnosis."""
    with pytest.raises(ValueError, match="at least one provider"):
        build_llm_client()
