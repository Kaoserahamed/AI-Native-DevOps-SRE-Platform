"""The provider interface every LLM adapter implements (ADR-0006).

An adapter has one job: translate :class:`~packages.llm.types.LlmRequest` into a provider call, translate
the answer back into :class:`~packages.llm.types.LlmResponse`, and map every failure onto the exception
taxonomy. Adapters do not retry, do not price, do not enforce budgets and do not decide which provider to
use — those live in :mod:`packages.llm.resilience`, so behaviour is identical for every provider.

``complete`` receives an absolute monotonic ``deadline``. An adapter must apply it to its transport (an
HTTP client timeout, for example) and raise :class:`~packages.llm.types.LlmTimeoutError` when it elapses,
so a hung provider cannot stall the control loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from packages.llm.structured import ModelT, parse_structured
from packages.llm.types import LlmRequest, LlmResponse


class LlmProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider identifier that appears in the audit trail."""

    @property
    @abstractmethod
    def supported_models(self) -> tuple[str, ...]:
        """Return the models this adapter can serve, most capable first."""

    @abstractmethod
    def complete(self, request: LlmRequest, *, deadline: float) -> LlmResponse:
        """Return one completion, or raise a subclass of :class:`~packages.llm.types.LlmError`."""

    def supports(self, model: str) -> bool:
        """Return whether the adapter advertises ``model``."""
        return model in self.supported_models

    def complete_structured(
        self, request: LlmRequest, schema: type[ModelT], *, deadline: float
    ) -> ModelT:
        """Return a schema-validated completion.

        The default implementation validates the text answer, which works for every provider. An adapter
        whose provider supports native structured output (JSON mode, tool schema) should override this and
        still return the same validated type.
        """
        return parse_structured(self.complete(request, deadline=deadline).content, schema)


__all__ = ["LlmProvider"]
