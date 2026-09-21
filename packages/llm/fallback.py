"""Provider fallback chain.

The documented fallback policy (ADR-0006): providers are tried in priority order — the primary first, then
each fallback — and only for retryable failures (timeout, rate limit, provider unavailable). A request that
the provider rejected as invalid is never replayed elsewhere, because another provider would reject it the
same way, and the answer records which provider actually served it.
"""

from __future__ import annotations

from collections.abc import Sequence
import logging

from packages.llm.provider import LlmProvider
from packages.llm.retry import RetryPolicy
from packages.llm.types import LlmError, LlmRequest, LlmResponse, LlmUnavailableError

logger = logging.getLogger("llm.fallback")


class FallbackLlmProvider(LlmProvider):
    """A provider chain that hides a provider incident from the control loop."""

    def __init__(self, providers: Sequence[LlmProvider]) -> None:
        if not providers:
            raise ValueError("a fallback chain requires at least one provider")
        self._providers: tuple[LlmProvider, ...] = tuple(providers)

    @property
    def providers(self) -> tuple[LlmProvider, ...]:
        """Return the chain in priority order."""
        return self._providers

    @property
    def name(self) -> str:
        """Return a chain description, e.g. ``fallback[openai->local]``."""
        return "fallback[" + "->".join(provider.name for provider in self._providers) + "]"

    @property
    def supported_models(self) -> tuple[str, ...]:
        """Return every model any provider in the chain advertises, without duplicates."""
        models: list[str] = []
        for provider in self._providers:
            models.extend(model for model in provider.supported_models if model not in models)
        return tuple(models)

    def complete(self, request: LlmRequest, *, deadline: float) -> LlmResponse:
        """Return the first provider answer, falling back only on retryable failures."""
        last_error: LlmError | None = None
        for index, provider in enumerate(self._providers):
            try:
                return provider.complete(request, deadline=deadline)
            except LlmError as error:
                if not RetryPolicy.is_retryable(error) or index == len(self._providers) - 1:
                    raise
                last_error = error
                logger.warning(
                    "provider %s failed with %s; falling back to %s",
                    provider.name,
                    type(error).__name__,
                    self._providers[index + 1].name,
                )
        raise LlmUnavailableError(f"no provider in {self.name} answered") from last_error


__all__ = ["FallbackLlmProvider"]
