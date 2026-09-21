"""Validation tests for the LLM interface value types."""

from __future__ import annotations

from typing import Final

import pytest

from packages.llm import (
    MAX_MESSAGES,
    ChatMessage,
    LlmRequest,
    LlmResponse,
    ModelConfig,
    Role,
    Usage,
)

pytestmark = pytest.mark.unit

FAKE_CONFIG: Final[ModelConfig] = ModelConfig(provider="fake", model="fake-model")


def test_message_serializes_to_the_provider_neutral_shape() -> None:
    """A message carries a role and bounded content, and converts to the shared wire shape."""
    message = ChatMessage(role=Role.SYSTEM, content="You are an SRE assistant.")
    assert message.as_dict() == {"role": "system", "content": "You are an SRE assistant."}


@pytest.mark.parametrize("content", ["", "   ", "\n\t"])
def test_message_rejects_blank_content(content: str) -> None:
    """A blank message is a bug in the caller, not a valid prompt."""
    with pytest.raises(ValueError, match="must not be blank"):
        ChatMessage(role=Role.USER, content=content)


def test_message_rejects_unbounded_content() -> None:
    """Message content is bounded so one incident cannot exhaust the prompt budget."""
    with pytest.raises(ValueError, match="must not exceed"):
        ChatMessage(role=Role.USER, content="x" * 100_001)


def test_model_config_exposes_the_audit_reference() -> None:
    """The provider/model reference recorded in the audit trail is derived, not duplicated."""
    assert FAKE_CONFIG.model_ref == "fake/fake-model"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"provider": "  "}, "provider must not be blank"),
        ({"model": ""}, "model must not be blank"),
        ({"max_tokens": 0}, "max_tokens must be at least 1"),
        ({"temperature": -0.1}, "temperature must be between"),
        ({"temperature": 3.0}, "temperature must be between"),
        ({"top_p": 0.0}, "top_p must be greater"),
        ({"top_p": 1.5}, "top_p must be greater"),
        ({"timeout_seconds": 0.0}, "timeout_seconds must be positive"),
    ],
)
def test_model_config_rejects_invalid_values(overrides: dict[str, object], message: str) -> None:
    """Every field of a model configuration is validated before a call is made."""
    values: dict[str, object] = {"provider": "fake", "model": "fake-model"}
    values.update(overrides)
    with pytest.raises(ValueError, match=message):
        ModelConfig(**values)  # type: ignore[arg-type]


def test_request_requires_at_least_one_message() -> None:
    """A request without messages could never produce a diagnosis."""
    with pytest.raises(ValueError, match="at least one message"):
        LlmRequest(model_config=FAKE_CONFIG, messages=())


def test_request_rejects_too_many_messages() -> None:
    """The conversation length is bounded, which bounds the prompt budget."""
    messages = tuple(ChatMessage(role=Role.USER, content="tick") for _ in range(MAX_MESSAGES + 1))
    with pytest.raises(ValueError, match=f"at most {MAX_MESSAGES} messages"):
        LlmRequest(model_config=FAKE_CONFIG, messages=messages)


def test_request_counts_prompt_characters() -> None:
    """Prompt size is measurable without a provider, which is what the budget check uses."""
    request = LlmRequest(
        model_config=FAKE_CONFIG,
        messages=(
            ChatMessage(role=Role.SYSTEM, content="abc"),
            ChatMessage(role=Role.USER, content="defg"),
        ),
    )
    assert request.prompt_characters() == 7


def test_usage_totals_and_accumulates() -> None:
    """Usage is additive so a run's totals are exact sums of its calls."""
    first = Usage(prompt_tokens=100, completion_tokens=20, cost_usd=0.001)
    second = Usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.0005)
    assert first.total_tokens == 120
    assert (first + second) == Usage(prompt_tokens=110, completion_tokens=25, cost_usd=0.0015)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"prompt_tokens": -1}, "token counts must not be negative"),
        ({"completion_tokens": -1}, "token counts must not be negative"),
        ({"cost_usd": -0.01}, "cost_usd must not be negative"),
    ],
)
def test_usage_rejects_negative_accounting(overrides: dict[str, int], message: str) -> None:
    """Negative accounting would let a run appear to refund budget it already spent."""
    with pytest.raises(ValueError, match=message):
        Usage(**overrides)


def test_response_requires_at_least_one_attempt() -> None:
    """A response that claims zero attempts could not have come from a provider."""
    with pytest.raises(ValueError, match="attempts must be at least 1"):
        LlmResponse(
            content="{}",
            model_config=FAKE_CONFIG,
            usage=Usage(),
            provider="fake",
            attempts=0,
        )
