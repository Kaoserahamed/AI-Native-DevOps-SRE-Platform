"""Model pricing and cost accounting.

The interface prices a call from the token usage the adapter reports. A model without a committed price
raises :class:`~packages.llm.types.LlmPricingError` instead of accounting a silent zero, because an
unpriced model would quietly disable the per-incident cost ceiling that Phase 22.3 relies on.

The default table holds list prices in USD per million tokens and is intentionally small: it covers the
models the demo configuration names, and an operator adds a row (or an override) when they switch model.
Prices change upstream, so the table is data, not logic, and every entry names the revision it was read
from.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from packages.llm.types import LlmPricingError

PER_MILLION: Final[float] = 1_000_000.0


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """List price of one model, expressed per million tokens."""

    usd_per_million_prompt_tokens: float
    usd_per_million_completion_tokens: float

    def __post_init__(self) -> None:
        if self.usd_per_million_prompt_tokens < 0.0:
            raise ValueError("prompt token price must not be negative")
        if self.usd_per_million_completion_tokens < 0.0:
            raise ValueError("completion token price must not be negative")

    def cost_usd(self, *, prompt_tokens: int, completion_tokens: int) -> float:
        """Return the cost of a call with the given token counts."""
        if prompt_tokens < 0 or completion_tokens < 0:
            raise ValueError("token counts must not be negative")
        return (
            prompt_tokens * self.usd_per_million_prompt_tokens
            + completion_tokens * self.usd_per_million_completion_tokens
        ) / PER_MILLION


#: Illustrative list prices in USD per million tokens, used when no override is supplied.
#: They are configuration, not a claim about any provider's current invoice.
DEFAULT_PRICES: Final[Mapping[str, ModelPrice]] = {
    "gpt-4o-mini": ModelPrice(0.15, 0.60),
    "gpt-4o": ModelPrice(2.50, 10.00),
    "claude-3-5-sonnet": ModelPrice(3.00, 15.00),
    "claude-3-5-haiku": ModelPrice(0.80, 4.00),
    "llama3.1:8b-instruct": ModelPrice(0.0, 0.0),
    # The deterministic test double (packages/llm/fake.py) is priced at zero: it must never
    # contribute to a cost assertion, and it must never be mistaken for a real spend.
    "fake-model": ModelPrice(0.0, 0.0),
}


class PriceTable:
    """Resolves a model name to a price, with explicit overrides for tests and self-hosted models."""

    def __init__(
        self,
        prices: Mapping[str, ModelPrice] | None = None,
        *,
        overrides: Mapping[str, ModelPrice] | None = None,
    ) -> None:
        merged = dict(DEFAULT_PRICES if prices is None else prices)
        merged.update(overrides or {})
        self._prices: dict[str, ModelPrice] = merged

    def register(self, model: str, price: ModelPrice) -> None:
        """Add or replace the price of one model."""
        if not model.strip():
            raise ValueError("model must not be blank")
        self._prices[model] = price

    def price(self, model: str) -> ModelPrice:
        """Return the price of ``model``, or raise :class:`LlmPricingError`."""
        try:
            return self._prices[model]
        except KeyError as error:
            raise LlmPricingError(
                f"no price registered for model {model!r}; register one before calling it"
            ) from error

    def cost_usd(self, model: str, *, prompt_tokens: int, completion_tokens: int) -> float:
        """Return the cost of one call to ``model``."""
        return self.price(model).cost_usd(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        )

    def known_models(self) -> tuple[str, ...]:
        """Return the priced models in sorted order, for documentation and diagnostics."""
        return tuple(sorted(self._prices))


__all__ = [
    "DEFAULT_PRICES",
    "PER_MILLION",
    "ModelPrice",
    "PriceTable",
]
