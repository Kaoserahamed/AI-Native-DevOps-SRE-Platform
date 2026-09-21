"""Contract tests every provider adapter must satisfy (ADR-0006).

The behavioural suite lives here so an adapter cannot pass by behaving differently: it is parameterised over
the adapters the platform ships, and every new adapter is added to ``PROVIDER_FACTORIES`` in the same change
that introduces it. Timeout, retry, rate-limit and refusal behaviour is exercised against the shared
resilience layer in ``test_client.py`` and ``test_retry.py``, because that is where it is implemented; an
adapter only has to translate its wire format correctly, and that is what these tests pin down.
"""

from __future__ import annotations

from collections.abc import Callable
import inspect
from typing import Final

from pydantic import BaseModel
import pytest

from packages.llm import (
    ChatMessage,
    FakeLlmProvider,
    FallbackLlmProvider,
    LlmProvider,
    LlmRequest,
    ModelConfig,
    ResilientLlmProvider,
    Role,
)

pytestmark = pytest.mark.contract

#: Every shipped adapter, by name, so the suite is visibly parameterised over the real implementations.
PROVIDER_FACTORIES: Final[tuple[tuple[str, Callable[[], LlmProvider]], ...]] = (
    ("fake", FakeLlmProvider),
)

PROVIDER_IDS: Final[list[str]] = [name for name, _ in PROVIDER_FACTORIES]


class Outcome(BaseModel):
    """Schema used to check that every adapter supports structured output."""

    diagnosis: str
    confidence: float


@pytest.fixture
def request_for(model_config: ModelConfig) -> LlmRequest:
    """Return a representative diagnosis request."""
    return LlmRequest(
        model_config=model_config,
        messages=(
            ChatMessage(role=Role.SYSTEM, content="You are an SRE diagnosis assistant."),
            ChatMessage(role=Role.USER, content="Diagnose incident INC-2026-0001."),
        ),
    )


def test_interface_is_abstract_and_cannot_be_used_directly() -> None:
    """The interface is a contract, not a base implementation that silently does nothing."""
    assert inspect.isabstract(LlmProvider)
    assert {"name", "supported_models", "complete"} <= LlmProvider.__abstractmethods__


@pytest.mark.parametrize("adapter", [cls for _, cls in PROVIDER_FACTORIES], ids=PROVIDER_IDS)
def test_every_adapter_implements_the_interface(adapter: type[LlmProvider]) -> None:
    """An adapter that is not an :class:`LlmProvider` would not be usable by the client."""
    assert issubclass(adapter, LlmProvider)


@pytest.mark.parametrize(("adapter_name", "factory"), PROVIDER_FACTORIES, ids=PROVIDER_IDS)
def test_adapter_reports_an_identity(adapter_name: str, factory: Callable[[], LlmProvider]) -> None:
    """The audit trail needs a provider name and the models it can serve."""
    provider = factory()
    assert provider.name == adapter_name
    assert provider.supported_models
    assert provider.supports(provider.supported_models[0])
    assert not provider.supports("model-that-does-not-exist")


@pytest.mark.parametrize(("adapter_name", "factory"), PROVIDER_FACTORIES, ids=PROVIDER_IDS)
def test_adapter_answers_inside_the_deadline(
    adapter_name: str, factory: Callable[[], LlmProvider], request_for: LlmRequest, deadline: float
) -> None:
    """A response echoes the request's model configuration and reports its own usage."""
    response = factory().complete(request_for, deadline=deadline)
    assert response.content
    assert response.provider == adapter_name
    assert response.model_config == request_for.model_config
    assert response.usage.total_tokens > 0
    assert response.attempts == 1


@pytest.mark.parametrize(("adapter_name", "factory"), PROVIDER_FACTORIES, ids=PROVIDER_IDS)
def test_adapter_supports_structured_output(
    adapter_name: str, factory: Callable[[], LlmProvider], request_for: LlmRequest, deadline: float
) -> None:
    """Every adapter can return a schema-validated answer, natively or via the shared parser."""
    parsed = factory().complete_structured(request_for, Outcome, deadline=deadline)
    assert parsed.diagnosis == "insufficient_evidence"
    assert 0.0 <= parsed.confidence <= 1.0


def test_resilient_client_and_chain_expose_the_interface() -> None:
    """The wrappers are providers too, so they compose without special cases."""
    provider = FakeLlmProvider()
    chain = FallbackLlmProvider([provider])
    client = ResilientLlmProvider(chain)
    assert isinstance(client, LlmProvider)
    assert client.name == "resilient(fallback[fake])"
    assert client.supported_models == provider.supported_models
