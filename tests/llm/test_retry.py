"""Retry policy tests: what is retryable and how long to wait."""

from __future__ import annotations

import pytest

from packages.llm import (
    RETRYABLE_ERRORS,
    LlmBudgetExceededError,
    LlmError,
    LlmPricingError,
    LlmRateLimitError,
    LlmRequestError,
    LlmSchemaError,
    LlmTimeoutError,
    LlmUnavailableError,
    RetryPolicy,
)

pytestmark = pytest.mark.unit


def test_retryable_failures_are_the_transient_ones() -> None:
    """Timeouts, rate limits and provider outages can resolve on their own; nothing else can."""
    assert (LlmTimeoutError, LlmRateLimitError, LlmUnavailableError) == RETRYABLE_ERRORS
    assert RetryPolicy.is_retryable(LlmTimeoutError("slow"))
    assert RetryPolicy.is_retryable(LlmRateLimitError("busy"))
    assert RetryPolicy.is_retryable(LlmUnavailableError("down"))


@pytest.mark.parametrize(
    "error",
    [
        LlmRequestError("invalid request"),
        LlmBudgetExceededError("out of budget"),
        LlmPricingError("unpriced"),
        LlmSchemaError("bad answer"),
        RuntimeError("not an llm error"),
    ],
)
def test_deterministic_failures_are_not_retried(error: BaseException) -> None:
    """A retry would fail identically and, for a budget breach, would spend money to prove it."""
    assert not RetryPolicy.is_retryable(error)


def test_backoff_grows_exponentially_and_is_capped() -> None:
    """Repeated failures back off further, up to a ceiling that keeps a run inside its deadline."""
    policy = RetryPolicy(
        initial_backoff_seconds=0.5,
        backoff_multiplier=3.0,
        max_backoff_seconds=5.0,
        jitter_ratio=0.0,
    )
    assert policy.backoff_seconds(1, random_value=0.0) == pytest.approx(0.5)
    assert policy.backoff_seconds(2, random_value=0.0) == pytest.approx(1.5)
    assert policy.backoff_seconds(3, random_value=0.0) == pytest.approx(4.5)
    assert policy.backoff_seconds(4, random_value=0.0) == pytest.approx(5.0)


def test_jitter_spreads_retries_within_a_bounded_window() -> None:
    """Many workers failing against one provider must not retry in lockstep."""
    policy = RetryPolicy(initial_backoff_seconds=1.0, jitter_ratio=0.25, backoff_multiplier=1.0)
    assert policy.backoff_seconds(1, random_value=0.0) == pytest.approx(0.75)
    assert policy.backoff_seconds(1, random_value=0.5) == pytest.approx(1.0)
    assert policy.backoff_seconds(1, random_value=1.0) == pytest.approx(1.25)
    assert policy.backoff_seconds(1, random_value=99.0) == pytest.approx(1.25)
    assert policy.backoff_seconds(1, random_value=-1.0) == pytest.approx(0.75)


def test_backoff_rejects_an_invalid_attempt_number() -> None:
    """Attempt numbers are 1-based; zero would silently mean "retry the first attempt"."""
    with pytest.raises(ValueError, match="attempt must be at least 1"):
        RetryPolicy().backoff_seconds(0, random_value=0.0)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"max_attempts": 0}, "max_attempts must be at least 1"),
        ({"initial_backoff_seconds": -0.5}, "initial_backoff_seconds must not be negative"),
        ({"backoff_multiplier": 0.5}, "backoff_multiplier must be at least 1.0"),
        (
            {"initial_backoff_seconds": 2.0, "max_backoff_seconds": 1.0},
            "max_backoff_seconds must not be smaller",
        ),
        ({"jitter_ratio": 1.0}, "jitter_ratio must be in"),
        ({"jitter_ratio": -0.1}, "jitter_ratio must be in"),
    ],
)
def test_policy_rejects_unusable_configuration(overrides: dict[str, float], message: str) -> None:
    """A policy that cannot be applied is a configuration error, not a permissive default."""
    with pytest.raises(ValueError, match=message):
        RetryPolicy(**overrides)  # type: ignore[arg-type]


def test_default_policy_is_bounded() -> None:
    """The default policy retries a bounded number of times with bounded delays."""
    policy = RetryPolicy()
    assert policy.max_attempts == 3
    assert policy.max_backoff_seconds == pytest.approx(8.0)
    assert isinstance(LlmTimeoutError("t"), LlmError)
