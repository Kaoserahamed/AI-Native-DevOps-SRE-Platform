"""Shared fixtures for the LLM interface tests.

Every test in this tier is deterministic: the clock is a controllable double, no HTTP client is constructed
and the provider is the in-repository fake, so retry, fallback, budget and timeout behaviour can be asserted
exactly rather than observed approximately.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from packages.llm import (
    ChatMessage,
    FakeLlmProvider,
    LlmRequest,
    ModelConfig,
    Role,
    ScriptedReply,
    Usage,
)
from packages.test_fixtures.clock import FakeClock, SleepRecorder

#: Deadline used by tests that do not exercise the deadline itself.
DEADLINE_HORIZON_SECONDS = 60.0


@pytest.fixture
def clock() -> FakeClock:
    """Return a controllable monotonic clock."""
    return FakeClock()


@pytest.fixture
def sleep_recorder() -> SleepRecorder:
    """Return a recorder that captures backoff delays."""
    return SleepRecorder()


@pytest.fixture
def deadline(clock: FakeClock) -> float:
    """Return a deadline far enough ahead that only explicit tests reach it."""
    return clock.deadline_in(DEADLINE_HORIZON_SECONDS)


@pytest.fixture
def fake_provider() -> FakeLlmProvider:
    """Return the deterministic provider with one valid "insufficient evidence" answer scripted."""
    return FakeLlmProvider(
        script=[
            ScriptedReply(
                content='{"diagnosis": "insufficient_evidence", "confidence": 0.1}',
                usage=Usage(prompt_tokens=100, completion_tokens=20),
            )
        ]
    )


@pytest.fixture
def model_config() -> ModelConfig:
    """Return the configuration of the deterministic fake model."""
    return ModelConfig(provider="fake", model="fake-model", max_tokens=256, timeout_seconds=5.0)


@pytest.fixture
def build_request(model_config: ModelConfig) -> Callable[..., LlmRequest]:
    """Return a factory for requests with predictable messages."""

    def build(
        *contents: str, config: ModelConfig | None = None, role: Role = Role.USER
    ) -> LlmRequest:
        messages = (
            tuple(ChatMessage(role=role, content=content) for content in contents)
            if contents
            else (ChatMessage(role=role, content="analyze incident INC-2026-0001"),)
        )
        return LlmRequest(model_config=config or model_config, messages=messages)

    return build
