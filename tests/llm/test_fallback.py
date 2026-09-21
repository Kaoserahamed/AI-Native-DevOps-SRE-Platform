"""Provider fallback policy tests."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from packages.llm import (
    FakeLlmProvider,
    FallbackLlmProvider,
    LlmError,
    LlmRateLimitError,
    LlmRequest,
    LlmRequestError,
    LlmUnavailableError,
    ScriptedReply,
)

pytestmark = pytest.mark.unit


def _provider(name: str, *script: ScriptedReply | str | LlmError) -> FakeLlmProvider:
    """Return a fake provider with a name and a scripted outcome list."""
    return FakeLlmProvider(provider=name, script=script)


def test_chain_requires_at_least_one_provider() -> None:
    """An empty chain would silently disable diagnosis."""
    with pytest.raises(ValueError, match="at least one provider"):
        FallbackLlmProvider([])


def test_chain_reports_its_members_and_order() -> None:
    """The chain is auditable: the members and their priority are inspectable."""
    chain = FallbackLlmProvider([_provider("primary"), _provider("secondary")])
    assert [provider.name for provider in chain.providers] == ["primary", "secondary"]
    assert chain.name == "fallback[primary->secondary]"


def test_supported_models_are_deduplicated_in_priority_order() -> None:
    """Two providers serving the same model must not duplicate it in the advertised list."""
    chain = FallbackLlmProvider(
        [
            FakeLlmProvider(provider="primary", model="shared-model"),
            FakeLlmProvider(provider="secondary", model="shared-model"),
            FakeLlmProvider(provider="fallback", model="other-model"),
        ]
    )
    assert chain.supported_models == ("shared-model", "other-model")
    assert chain.supports("other-model")
    assert not chain.supports("absent-model")


def test_retryable_failure_moves_to_the_next_provider(
    build_request: Callable[..., LlmRequest], deadline: float
) -> None:
    """A provider incident must not stop the control loop."""
    primary = _provider("primary", LlmUnavailableError("outage"))
    secondary = _provider("secondary", "answer from the fallback")
    chain = FallbackLlmProvider([primary, secondary])

    response = chain.complete(build_request("diagnose"), deadline=deadline)

    assert response.provider == "secondary"
    assert response.content == "answer from the fallback"
    assert len(primary.calls) == 1


def test_invalid_request_is_not_replayed_on_another_provider(
    build_request: Callable[..., LlmRequest], deadline: float
) -> None:
    """Another provider would reject the same malformed request, so it is not retried."""
    primary = _provider("primary", LlmRequestError("malformed request"))
    secondary = _provider("secondary", "answer")
    chain = FallbackLlmProvider([primary, secondary])

    with pytest.raises(LlmRequestError):
        chain.complete(build_request("diagnose"), deadline=deadline)

    assert secondary.calls == ()


def test_failure_on_the_last_provider_is_raised_unchanged(
    build_request: Callable[..., LlmRequest], deadline: float
) -> None:
    """The caller sees the real reason the chain failed, not a synthetic wrapper."""
    chain = FallbackLlmProvider(
        [
            _provider("primary", LlmUnavailableError("outage")),
            _provider("secondary", LlmRateLimitError("busy")),
        ]
    )

    with pytest.raises(LlmRateLimitError):
        chain.complete(build_request("diagnose"), deadline=deadline)
