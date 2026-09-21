"""Structured-output parsing and validation.

Model output is untrusted input (TB-4): it is parsed as JSON and validated against a Pydantic schema before
any downstream code sees it, so a malformed or hostile answer becomes a typed failure instead of a silently
misinterpreted diagnosis. Nothing here executes model output, and no field of model output selects a tool
or a target (that is the policy engine's job).
"""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from packages.llm.types import LlmSchemaError

ModelT = TypeVar("ModelT", bound=BaseModel)

#: Models frequently wrap JSON in a Markdown fence even when asked for raw JSON. Accepting exactly one
#: fenced block is a tolerant-but-bounded convenience; anything else must be plain JSON.
_FENCED_BLOCK = re.compile(r"^\s*```(?:json)?\s*(?P<body>.+?)\s*```\s*$", re.DOTALL)


def extract_json_object(content: str) -> str:
    """Return the JSON object embedded in ``content``, or raise :class:`LlmSchemaError`."""
    text = content.strip()
    if not text:
        raise LlmSchemaError("model returned an empty response")
    fenced = _FENCED_BLOCK.match(text)
    if fenced is not None:
        text = fenced.group("body").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise LlmSchemaError("model response contains no JSON object")
    return text[start : end + 1]


def parse_structured(content: str, schema: type[ModelT]) -> ModelT:
    """Parse ``content`` into ``schema``, raising :class:`LlmSchemaError` on any deviation."""
    payload_text = extract_json_object(content)
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as error:
        raise LlmSchemaError(f"model response is not valid JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise LlmSchemaError("model response must be a JSON object")
    try:
        return schema.model_validate(payload)
    except ValidationError as error:
        raise LlmSchemaError(
            f"model response does not satisfy {schema.__name__}: "
            f"{error.error_count()} validation error(s)"
        ) from error


__all__ = ["ModelT", "extract_json_object", "parse_structured"]
