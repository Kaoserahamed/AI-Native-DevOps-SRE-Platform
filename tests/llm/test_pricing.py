"""Model pricing and cost accounting tests."""

from __future__ import annotations

import pytest

from packages.llm import DEFAULT_PRICES, LlmPricingError, ModelPrice, PriceTable

pytestmark = pytest.mark.unit


def test_price_is_per_million_tokens() -> None:
    """Cost is computed in the unit the providers publish, so the table stays a data change."""
    price = ModelPrice(3.00, 15.00)
    assert price.cost_usd(prompt_tokens=1_000_000, completion_tokens=1_000_000) == pytest.approx(
        18.0
    )
    assert price.cost_usd(prompt_tokens=1_000, completion_tokens=1_000) == pytest.approx(0.018)


@pytest.mark.parametrize(
    ("prompt_price", "completion_price"),
    [(-0.01, 1.0), (1.0, -0.01)],
)
def test_negative_prices_are_rejected(prompt_price: float, completion_price: float) -> None:
    """A negative price would credit the run's cost ceiling."""
    with pytest.raises(ValueError, match="must not be negative"):
        ModelPrice(prompt_price, completion_price)


def test_negative_token_counts_are_rejected() -> None:
    """Token counts are counters; a negative value is a bug in the adapter."""
    with pytest.raises(ValueError, match="token counts must not be negative"):
        ModelPrice(1.0, 1.0).cost_usd(prompt_tokens=-1, completion_tokens=0)


def test_table_exposes_the_committed_prices() -> None:
    """The default table is the documented starting point and is queryable for review."""
    table = PriceTable()
    assert "gpt-4o-mini" in table.known_models()
    assert set(table.known_models()) == set(DEFAULT_PRICES)


def test_unpriced_model_fails_instead_of_accounting_zero() -> None:
    """A model without a price must stop the run, not silently disable the cost ceiling."""
    with pytest.raises(LlmPricingError, match="no price registered"):
        PriceTable().price("unregistered-model")


def test_unknown_model_cost_lookup_fails() -> None:
    """Cost lookups go through the same guard as price lookups."""
    with pytest.raises(LlmPricingError):
        PriceTable().cost_usd("unregistered-model", prompt_tokens=1, completion_tokens=1)


def test_register_adds_a_price_for_a_self_hosted_or_new_model() -> None:
    """Operators extend the table rather than editing code."""
    table = PriceTable()
    table.register("local-model", ModelPrice(0.0, 0.0))
    assert table.cost_usd("local-model", prompt_tokens=10_000, completion_tokens=10_000) == 0.0


def test_register_rejects_a_blank_model_name() -> None:
    """A blank key would be unreachable and hide a configuration mistake."""
    with pytest.raises(ValueError, match="model must not be blank"):
        PriceTable().register("  ", ModelPrice(0.0, 0.0))


def test_overrides_replace_the_default_price() -> None:
    """Tests and negotiated enterprise prices override the list price without editing it."""
    table = PriceTable(overrides={"gpt-4o-mini": ModelPrice(0.0, 0.0)})
    assert table.cost_usd("gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=0) == 0.0


def test_explicit_table_ignores_the_defaults() -> None:
    """A caller that supplies its own table gets exactly that table."""
    table = PriceTable({"only-model": ModelPrice(1.0, 2.0)})
    assert table.known_models() == ("only-model",)
    with pytest.raises(LlmPricingError):
        table.price("gpt-4o-mini")


def test_fake_model_is_priced_at_zero() -> None:
    """The deterministic test double must never contribute to a cost assertion."""
    assert (
        PriceTable().cost_usd("fake-model", prompt_tokens=1_000_000, completion_tokens=1_000_000)
        == 0.0
    )
