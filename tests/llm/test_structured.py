"""Structured-output parsing tests.

Model output is untrusted input: it must either validate against the requested schema or fail with a typed
error. These tests cover the tolerant cases (a fenced block, surrounding prose) and the hostile ones
(not JSON at all, JSON of the wrong shape, a schema violation).
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict
import pytest

from packages.llm import (
    ChatMessage,
    FakeLlmProvider,
    LlmRequest,
    LlmSchemaError,
    ModelConfig,
    Role,
    parse_structured,
)

pytestmark = pytest.mark.unit

VALID: Final[str] = '{"diagnosis": "dependency_failure", "confidence": 0.8}'


class Diagnosis(BaseModel):
    """Minimal stand-in for the agent's structured diagnosis schema."""

    model_config = ConfigDict(extra="forbid")

    diagnosis: str
    confidence: float


def test_plain_json_object_is_parsed() -> None:
    """The happy path returns a validated model."""
    parsed = parse_structured(VALID, Diagnosis)
    assert parsed.diagnosis == "dependency_failure"
    assert parsed.confidence == pytest.approx(0.8)


def test_fenced_json_block_is_parsed() -> None:
    """Models often wrap JSON in a Markdown fence even when asked not to."""
    parsed = parse_structured(f"```json\n{VALID}\n```", Diagnosis)
    assert parsed.diagnosis == "dependency_failure"


def test_surrounding_prose_is_tolerated() -> None:
    """Explanatory prose around exactly one JSON object is accepted."""
    parsed = parse_structured(
        f"Here is my analysis:\n{VALID}\nLet me know if you need more.", Diagnosis
    )
    assert parsed.confidence == pytest.approx(0.8)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "   ",
        "I cannot analyse this incident.",
        "{not valid json}",
        "[1, 2, 3]",
        '{"diagnosis": "dependency_failure"}',
        '{"diagnosis": "dependency_failure", "confidence": "high"}',
        '{"diagnosis": "dependency_failure", "confidence": 0.5, "extra": true}',
    ],
)
def test_invalid_output_raises_a_schema_error(content: str) -> None:
    """Anything that is not a schema-valid JSON object becomes a typed failure."""
    with pytest.raises(LlmSchemaError):
        parse_structured(content, Diagnosis)


def test_validation_error_names_the_schema() -> None:
    """The error explains which schema rejected the answer, for the audit trail."""
    with pytest.raises(LlmSchemaError, match="Diagnosis"):
        parse_structured('{"confidence": "high"}', Diagnosis)


def test_provider_structured_completion_uses_the_shared_parser(
    fake_provider: FakeLlmProvider,
) -> None:
    """An adapter without a native structured-output mode still returns a validated model."""
    request = LlmRequest(
        model_config=ModelConfig(provider="fake", model="fake-model"),
        messages=(ChatMessage(role=Role.USER, content="diagnose INC-2026-0001"),),
    )
    parsed = fake_provider.complete_structured(request, Diagnosis, deadline=1_100.0)
    assert parsed.diagnosis == "insufficient_evidence"
