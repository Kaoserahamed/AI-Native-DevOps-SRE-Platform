"""Tests for the deterministic provider used by every other tier."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel
import pytest

from packages.llm import (
    DEFAULT_CONTENT,
    FakeLlmProvider,
    LlmRequest,
    LlmSchemaError,
    LlmTimeoutError,
    LlmUnavailableError,
    ScriptedReply,
    Usage,
    fingerprint,
)
from packages.test_fixtures.clock import FakeClock

pytestmark = pytest.mark.unit


def test_default_answer_is_the_honest_no_analysis_outcome(
    build_request: Callable[..., LlmRequest], deadline: float
) -> None:
    """Without a script the fake reports insufficient evidence rather than inventing a diagnosis."""
    response = FakeLlmProvider().complete(build_request("diagnose"), deadline=deadline)
    assert response.content == DEFAULT_CONTENT
    assert response.provider == "fake"
    assert response.usage.prompt_tokens > 0


def test_script_is_consumed_in_order(
    build_request: Callable[..., LlmRequest], deadline: float
) -> None:
    """A script lets one test drive "first attempt fails, second succeeds"."""
    provider = FakeLlmProvider(
        script=[
            LlmUnavailableError("provider outage"),
            ScriptedReply(
                content="second answer", usage=Usage(prompt_tokens=7, completion_tokens=3)
            ),
        ]
    )
    with pytest.raises(LlmUnavailableError):
        provider.complete(build_request("diagnose"), deadline=deadline)
    response = provider.complete(build_request("diagnose"), deadline=deadline)
    assert response.content == "second answer"
    assert response.usage.total_tokens == 10
    assert provider.remaining_script == 0


def test_plain_string_script_entries_are_answers(
    build_request: Callable[..., LlmRequest], deadline: float
) -> None:
    """A script can be written without wrapping every answer in a value object."""
    provider = FakeLlmProvider(script=["first", "second"])
    assert provider.complete(build_request(), deadline=deadline).content == "first"
    assert provider.complete(build_request(), deadline=deadline).content == "second"


def test_fingerprint_map_answers_matching_requests(
    build_request: Callable[..., LlmRequest], deadline: float
) -> None:
    """Fixture files key their canned answers by request fingerprint, so order does not matter."""
    request = build_request("incident INC-2026-0001")
    provider = FakeLlmProvider(responses={fingerprint(request): "mapped answer"})
    assert provider.complete(request, deadline=deadline).content == "mapped answer"
    assert (
        provider.complete(build_request("other prompt"), deadline=deadline).content
        == DEFAULT_CONTENT
    )


def test_every_request_is_recorded(
    fake_provider: FakeLlmProvider, build_request: Callable[..., LlmRequest], deadline: float
) -> None:
    """Tests assert what the platform actually sent, not what it meant to send."""
    request = build_request("diagnose INC-2026-0001")
    fake_provider.complete(request, deadline=deadline)
    assert fake_provider.calls == (request,)


def test_provider_identity_and_model_advertisement(fake_provider: FakeLlmProvider) -> None:
    """The fake advertises the provider name and model the audit trail records."""
    assert fake_provider.name == "fake"
    assert fake_provider.supported_models == ("fake-model",)
    assert fake_provider.supports("fake-model")
    assert not fake_provider.supports("gpt-4o")


def test_slow_answer_reports_a_timeout(
    build_request: Callable[..., LlmRequest], clock: FakeClock
) -> None:
    """An adapter that cannot answer inside the deadline raises a timeout, not a late answer."""
    provider = FakeLlmProvider(latency_seconds=2.0, clock=clock)
    with pytest.raises(LlmTimeoutError, match="deadline allows"):
        provider.complete(build_request("diagnose"), deadline=clock.deadline_in(1.0))


def test_negative_latency_is_rejected() -> None:
    """A negative latency would make the fake report time that never passed."""
    with pytest.raises(ValueError, match="latency_seconds must not be negative"):
        FakeLlmProvider(latency_seconds=-1.0)


class Outcome(BaseModel):
    """Minimal schema used to check that scripted answers are validated."""

    diagnosis: str


def test_structured_completion_rejects_invalid_scripted_answers(
    build_request: Callable[..., LlmRequest], deadline: float
) -> None:
    """A scripted answer that violates the schema surfaces as a schema error."""
    provider = FakeLlmProvider(script=["not json at all"])
    with pytest.raises(LlmSchemaError):
        provider.complete_structured(build_request("diagnose"), Outcome, deadline=deadline)


def test_structured_completion_returns_a_validated_model(
    build_request: Callable[..., LlmRequest], deadline: float
) -> None:
    """The default structured path validates the text answer for any adapter."""
    provider = FakeLlmProvider(script=['{"diagnosis": "dependency_failure"}'])
    parsed = provider.complete_structured(build_request("diagnose"), Outcome, deadline=deadline)
    assert parsed.diagnosis == "dependency_failure"
