"""Tests for the LLM provider abstraction.

(Phase 8.1 — unit tests for LLM interface.)
"""

from __future__ import annotations

import json
import pytest

from services.llm.app.llm import (
    LlmError,
    LlmProviderError,
    LlmRateLimitError,
    LlmRequest,
    LlmResponse,
    LlmTimeoutError,
    LlmProvider,
    ModelConfig,
    TokenBudget,
    TokenBudgetExceeded,
    Usage,
    FakeLlmProvider,
)


class DummySchema:
    """A minimal stand-in for a Pydantic model used in schema-validation tests."""

    @classmethod
    def model_validate(cls, data: dict) -> "DummySchema":
        if "diagnosis" not in data:
            raise ValueError("missing diagnosis")
        return cls()


class TestModelConfig:
    def test_defaults(self) -> None:
        cfg = ModelConfig(provider="openai", model="gpt-4")
        assert cfg.max_tokens == 4096
        assert cfg.temperature == 0.0
        assert cfg.top_p == 1.0

    def test_frozen(self) -> None:
        cfg = ModelConfig(provider="openai", model="gpt-4")
        with pytest.raises(Exception):
            cfg.model = "other"


class TestUsage:
    def test_defaults(self) -> None:
        u = Usage()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.cost_usd == 0.0


class TestLlmRequest:
    def test_schema_optional(self) -> None:
        cfg = ModelConfig(provider="openai", model="gpt-4")
        req = LlmRequest(messages=[{"role": "user", "content": "hello"}], model_config=cfg)
        assert req.schema is None


class TestLlmResponse:
    def test_defaults(self) -> None:
        r = LlmResponse(content="{}", usage=Usage())
        assert r.raw_response == {}


class TestFakeLlmProvider:
    def test_provider_name(self) -> None:
        p = FakeLlmProvider()
        assert p.provider_name == "fake"

    def test_supported_models(self) -> None:
        p = FakeLlmProvider()
        assert "fake-model" in p.supported_models

    def test_complete_returns_default_when_no_response_configured(self) -> None:
        p = FakeLlmProvider()
        cfg = ModelConfig(provider="fake", model="fake-model")
        req = LlmRequest(
            messages=[{"role": "user", "content": "analyze this incident"}],
            model_config=cfg,
        )
        resp = p.complete(req)
        data = json.loads(resp.content)
        assert data["diagnosis"] == "unknown"
        assert resp.usage.prompt_tokens == 100

    def test_complete_returns_configured_response(self) -> None:
        p = FakeLlmProvider(responses={
            "a" * 16: '{"diagnosis": "dependency_failure", "confidence": 0.85, "summary": "Redis is down"}'
        })
        cfg = ModelConfig(provider="fake", model="fake-model")
        req = LlmRequest(
            messages=[{"role": "user", "content": "analyze this incident"}],
            model_config=cfg,
        )
        resp = p.complete(req)
        data = json.loads(resp.content)
        assert data["diagnosis"] == "dependency_failure"
        assert data["confidence"] == 0.85


class TestTokenBudget:
    def test_defaults(self) -> None:
        b = TokenBudget()
        assert b.max_prompt_tokens == 100_000
        assert b.max_completion_tokens == 20_000
        assert b.max_cost_usd == 5.0

    def test_invalid_budget_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            TokenBudget(max_prompt_tokens=0)
        with pytest.raises(ValueError, match="positive"):
            TokenBudget(max_completion_tokens=-1)
        with pytest.raises(ValueError, match="non-negative"):
            TokenBudget(max_cost_usd=-1.0)

    def test_exceeds_prompt_budget(self) -> None:
        b = TokenBudget(max_prompt_tokens=100)
        cfg = ModelConfig(provider="fake", model="m")
        request = LlmRequest(
            messages=[{"role": "user", "content": "x" * 200}],
            model_config=cfg,
        )
        usage = Usage(prompt_tokens=50)
        with pytest.raises(TokenBudgetExceeded):
            b.check(request, usage)

    def test_exceeds_completion_budget(self) -> None:
        b = TokenBudget(max_completion_tokens=10)
        cfg = ModelConfig(provider="fake", model="m", max_tokens=100)
        request = LlmRequest(
            messages=[{"role": "user", "content": "hi"}],
            model_config=cfg,
        )
        usage = Usage(prompt_tokens=0)
        with pytest.raises(TokenBudgetExceeded):
            b.check(request, usage)

    def test_within_budget_allows_request(self) -> None:
        b = TokenBudget(max_prompt_tokens=1000, max_completion_tokens=500)
        cfg = ModelConfig(provider="fake", model="m", max_tokens=100)
        request = LlmRequest(
            messages=[{"role": "user", "content": "hi"}],
            model_config=cfg,
        )
        usage = Usage(prompt_tokens=10)
        # Should not raise
        b.check(request, usage)


class TestLlmExceptionHierarchy:
    def test_timeout_is_error(self) -> None:
        assert isinstance(LlmTimeoutError("t"), LlmError)

    def test_rate_limit_is_error(self) -> None:
        assert isinstance(LlmRateLimitError("r"), LlmError)

    def test_provider_error_is_error(self) -> None:
        assert isinstance(LlmProviderError("p"), LlmError)
