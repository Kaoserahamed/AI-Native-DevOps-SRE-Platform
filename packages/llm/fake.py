"""A deterministic in-process provider for unit, contract and evaluation tests (ADR-0006).

The platform must be demonstrable in CI without calling a paid API, and a retry, fallback or timeout test must
not depend on a real provider misbehaving. :class:`FakeLlmProvider` therefore answers from a script the test
supplies, records every request it received, and can be told to raise any interface error at a chosen point.

Resolution order for each call:

1. the next scripted outcome (a reply, or an error to raise);
2. ``responses[fingerprint(request)]`` when a fingerprint map is supplied;
3. ``default_content``.

Replies are consumed in order, so a test can script "rate limit, then success" and assert that the retry
occurred without a network call.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import time
from typing import Final

from packages.llm.budget import estimate_tokens
from packages.llm.provider import LlmProvider
from packages.llm.types import LlmError, LlmRequest, LlmResponse, LlmTimeoutError, Usage

#: Answer used when a test scripts nothing: the honest "no analysis available" outcome.
DEFAULT_CONTENT: Final[str] = (
    '{"diagnosis": "insufficient_evidence", "confidence": 0.0, "summary": "No analysis available"}'
)


@dataclass(frozen=True, slots=True)
class ScriptedReply:
    """A canned answer, optionally with exact token counts for cost assertions."""

    content: str
    usage: Usage | None = None
    finish_reason: str | None = "stop"


def fingerprint(request: LlmRequest) -> str:
    """Return a stable digest of a request, used to key canned answers in fixtures."""
    payload = {
        "provider": request.model_config.provider,
        "model": request.model_config.model,
        "messages": [message.as_dict() for message in request.messages],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


class FakeLlmProvider(LlmProvider):
    """A provider whose behaviour is entirely determined by the test."""

    def __init__(
        self,
        *,
        provider: str = "fake",
        model: str = "fake-model",
        script: Sequence[ScriptedReply | str | LlmError] = (),
        responses: Mapping[str, str] | None = None,
        default_content: str = DEFAULT_CONTENT,
        latency_seconds: float = 0.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if latency_seconds < 0.0:
            raise ValueError("latency_seconds must not be negative")
        self._provider = provider
        self._model = model
        self._script: list[ScriptedReply | str | LlmError] = list(script)
        self._responses = dict(responses or {})
        self._default_content = default_content
        self._latency_seconds = latency_seconds
        self._clock = clock
        self._calls: list[LlmRequest] = []

    @property
    def name(self) -> str:
        """Return the fake provider identifier used in the audit trail."""
        return self._provider

    @property
    def supported_models(self) -> tuple[str, ...]:
        """Return the single configured model."""
        return (self._model,)

    @property
    def calls(self) -> tuple[LlmRequest, ...]:
        """Return every request this provider received, in order."""
        return tuple(self._calls)

    @property
    def remaining_script(self) -> int:
        """Return how many scripted outcomes have not been consumed yet."""
        return len(self._script)

    def complete(self, request: LlmRequest, *, deadline: float) -> LlmResponse:
        """Return the next scripted answer, or raise the next scripted error."""
        self._calls.append(request)
        started = self._clock()
        outcome = self._next_outcome(request)
        if isinstance(outcome, LlmError):
            raise outcome
        # A simulated call only needs the deadline check when it claims to take time. Comparing clocks that a
        # test did not align would otherwise report a timeout for an instantaneous answer, so a test that sets
        # `latency_seconds` must pass the same clock the client uses.
        if self._latency_seconds > 0.0 and started + self._latency_seconds > deadline:
            raise LlmTimeoutError(
                f"fake provider needs {self._latency_seconds}s but the deadline allows "
                f"{deadline - started:.3f}s"
            )

        usage = outcome.usage
        if usage is None:
            usage = Usage(
                prompt_tokens=sum(estimate_tokens(m.content) for m in request.messages),
                completion_tokens=estimate_tokens(outcome.content),
            )
        return LlmResponse(
            content=outcome.content,
            model_config=request.model_config,
            usage=usage,
            provider=self._provider,
            finish_reason=outcome.finish_reason,
            latency_ms=int(self._latency_seconds * 1000),
        )

    def _next_outcome(self, request: LlmRequest) -> ScriptedReply | LlmError:
        """Return the outcome for this call without consuming the provider's recorded calls."""
        if self._script:
            return _as_reply(self._script.pop(0))
        mapped = self._responses.get(fingerprint(request))
        if mapped is not None:
            return ScriptedReply(content=mapped)
        return ScriptedReply(content=self._default_content)


def _as_reply(outcome: ScriptedReply | str | LlmError) -> ScriptedReply | LlmError:
    """Normalise a scripted outcome, keeping errors as errors."""
    if isinstance(outcome, LlmError):
        return outcome
    if isinstance(outcome, ScriptedReply):
        return outcome
    return ScriptedReply(content=outcome)


__all__ = [
    "DEFAULT_CONTENT",
    "FakeLlmProvider",
    "ScriptedReply",
    "fingerprint",
]
