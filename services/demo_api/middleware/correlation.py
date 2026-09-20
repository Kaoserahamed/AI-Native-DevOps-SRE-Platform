"""Correlation ID middleware and helpers.

Extracts or generates a request correlation ID (``X-Request-ID``) on every
request and stores it in a context-local ``contextvars.ContextVar`` so that
loggers, middleware and route handlers can correlate activity across async
boundaries without threading the ID through every function call.
"""

from __future__ import annotations

from contextvars import ContextVar
import logging
from typing import Any
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("demo-api.middleware")

_request_correlation_id: ContextVar[str | None] = ContextVar(
    "_request_correlation_id", default=None
)

CORRELATION_HEADER = "X-Request-ID"


def get_correlation_id() -> str | None:
    """Return the current request's correlation ID, if one is set."""
    return _request_correlation_id.get()


class CorrelationIdMiddleware:
    """Middleware that manages the request correlation ID lifecycle."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        raw_correlation = headers.get(CORRELATION_HEADER.lower().encode())
        if raw_correlation:
            correlation_id = raw_correlation.decode("utf-8")
        else:
            correlation_id = uuid.uuid4().hex

        # Replace any existing header so downstream handlers see exactly one ID.
        filtered = [
            (name, value)
            for name, value in scope.get("headers", [])
            if name.lower() != CORRELATION_HEADER.lower().encode()
        ]
        encoded = correlation_id.encode("utf-8")
        scope["headers"] = [
            *filtered,
            (CORRELATION_HEADER.lower().encode(), encoded),
        ]

        async def send_with_correlation(message: Message) -> None:
            if message["type"] == "http.response.start":
                raw_headers = message.setdefault("headers", [])
                existing = {name.lower() for name, _ in raw_headers if isinstance(name, bytes)}
                if CORRELATION_HEADER.lower().encode() not in existing:
                    raw_headers.append((CORRELATION_HEADER.lower().encode(), encoded))
            await send(message)

        token: Any = _request_correlation_id.set(correlation_id)
        logger.debug("Starting request %s", correlation_id)
        try:
            await self.app(scope, receive, send_with_correlation)
        finally:
            _request_correlation_id.reset(token)
            logger.debug("Completed request %s", correlation_id)
