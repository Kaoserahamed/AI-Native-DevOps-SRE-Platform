"""Budget estimation and per-run accounting tests."""

from __future__ import annotations

from typing import Final

import pytest

from packages.llm import (
    ChatMessage,
    LlmBudget,
    LlmBudgetExceededError,
    LlmRequest,
    LlmResponse,
    ModelConfig,
    Role,
    Usage,
    UsageLedger,
    estimate_tokens,
)
from packages.test_fixtures.clock import FakeClock

pytestmark = pytest.mark.unit

CONFIG: Final[ModelConfig] = ModelConfig(provider="fake", model="fake-model", max_tokens=100)


def _request(content: str) -> LlmRequest:
    """Return a one-message request carrying ``content``."""
    return LlmRequest(model_config=CONFIG, messages=(ChatMessage(role=Role.USER, content=content),))


def _response(usage: Usage) -> LlmResponse:
    """Return a fake response carrying explicit usage."""
    return LlmResponse(content="{}", model_config=CONFIG, usage=usage, provider="fake")


def test_empty_text_costs_nothing_to_estimate() -> None:
    """An empty string contributes no tokens."""
    assert estimate_tokens("") == 0


@pytest.mark.parametrize(
    ("text", "expected"), [("abcd", 1), ("abcde", 2), ("a" * 80, 20), ("a" * 81, 21)]
)
def test_token_estimate_rounds_up(text: str, expected: int) -> None:
    """Estimation rounds up, so a budget breach is detected early rather than late."""
    assert estimate_tokens(text) == expected


def test_token_estimate_rejects_a_non_positive_ratio() -> None:
    """A zero ratio would divide by zero instead of failing loudly."""
    with pytest.raises(ValueError, match="chars_per_token must be positive"):
        estimate_tokens("text", chars_per_token=0.0)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"max_prompt_tokens": 0}, "max_prompt_tokens must be at least 1"),
        ({"max_completion_tokens": 0}, "max_completion_tokens must be at least 1"),
        ({"max_cost_usd": -1.0}, "max_cost_usd must not be negative"),
        ({"max_calls": 0}, "max_calls must be at least 1"),
        ({"max_wall_clock_seconds": 0.0}, "max_wall_clock_seconds must be positive"),
    ],
)
def test_budget_rejects_unenforceable_ceilings(overrides: dict[str, float], message: str) -> None:
    """A ceiling that cannot be enforced is a configuration error, not a permissive default."""
    with pytest.raises(ValueError, match=message):
        LlmBudget(**overrides)  # type: ignore[arg-type]


def test_ledger_tracks_the_run_clock_and_remaining_cost(clock: FakeClock) -> None:
    """The ledger knows when the run started, when it must stop, and what is left to spend."""
    ledger = UsageLedger(LlmBudget(max_cost_usd=1.0, max_wall_clock_seconds=30.0), clock=clock)
    assert ledger.started_at == clock.current
    assert ledger.deadline == pytest.approx(clock.current + 30.0)
    assert ledger.remaining_cost_usd == pytest.approx(1.0)

    clock.advance(4.0)
    assert ledger.elapsed_seconds() == pytest.approx(4.0)

    ledger.record(_response(Usage(cost_usd=0.25)))
    assert ledger.remaining_cost_usd == pytest.approx(0.75)
    assert ledger.usage.cost_usd == pytest.approx(0.25)
    assert ledger.calls == 1


def test_ledger_allows_a_call_inside_the_budget(clock: FakeClock) -> None:
    """A compliant call passes every check."""
    UsageLedger(LlmBudget(), clock=clock).check(_request("short prompt"))


def test_ledger_refuses_a_call_once_the_call_budget_is_used(clock: FakeClock) -> None:
    """The call ceiling stops a loop that keeps asking for another diagnosis."""
    ledger = UsageLedger(LlmBudget(max_calls=1), clock=clock)
    ledger.record(_response(Usage()))
    with pytest.raises(LlmBudgetExceededError, match="call budget exhausted"):
        ledger.check(_request("again"))


def test_ledger_refuses_a_call_after_the_wall_clock_budget(clock: FakeClock) -> None:
    """Wall-clock budget is enforced before spending on a call that cannot finish in time."""
    ledger = UsageLedger(LlmBudget(max_wall_clock_seconds=0.5), clock=clock)
    assert ledger.deadline == pytest.approx(clock.current + 0.5)
    clock.advance(0.5)
    with pytest.raises(LlmBudgetExceededError, match="wall-clock budget exhausted"):
        ledger.check(_request("too late"))


def test_ledger_refuses_a_call_that_asks_for_too_many_completion_tokens(
    clock: FakeClock,
) -> None:
    """A request that exceeds the completion ceiling is refused before the provider is asked."""
    ledger = UsageLedger(LlmBudget(max_completion_tokens=50), clock=clock)
    with pytest.raises(LlmBudgetExceededError, match="exceeds the completion budget"):
        ledger.check(_request("generate a long report"))


def test_ledger_refuses_a_prompt_that_exceeds_the_token_budget(clock: FakeClock) -> None:
    """The estimated prompt size is checked against what the run has already spent."""
    ledger = UsageLedger(LlmBudget(max_prompt_tokens=100), clock=clock)
    with pytest.raises(LlmBudgetExceededError, match="prompt budget exceeded"):
        ledger.check(_request("x" * 500))


def test_ledger_accumulates_across_calls(clock: FakeClock) -> None:
    """Totals are exact sums, so a per-incident cost report is trustworthy."""
    ledger = UsageLedger(LlmBudget(), clock=clock)
    ledger.record(_response(Usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.01)))
    ledger.record(_response(Usage(prompt_tokens=1, completion_tokens=2, cost_usd=0.02)))
    assert ledger.usage.prompt_tokens == 11
    assert ledger.usage.completion_tokens == 7
    assert ledger.usage.cost_usd == pytest.approx(0.03)
    assert ledger.calls == 2


def test_ledger_projects_the_prompt_tokens_of_the_next_call(clock: FakeClock) -> None:
    """The projection includes the tokens already spent in this run."""
    ledger = UsageLedger(LlmBudget(), clock=clock)
    ledger.record(_response(Usage(prompt_tokens=10)))
    assert ledger.projected_prompt_tokens(_request("a" * 40)) == 20


def test_default_budget_is_bounded() -> None:
    """The defaults are finite: an unconfigured run cannot spend without limit."""
    budget = LlmBudget()
    assert budget.max_calls == 8
    assert budget.max_cost_usd == pytest.approx(5.0)
    assert budget.max_wall_clock_seconds == pytest.approx(120.0)
