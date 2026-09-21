"""HTTP observability middleware: metrics, tracing spans and correlation.

A single middleware records every HTTP response exactly once, so route
handlers never touch ``http_*`` series directly. This is what makes
``request count``, ``request latency`` and ``4xx/5xx rate`` trustworthy:
even unhandled exceptions and validation errors pass through here.

Endpoint labels use the route template (``/items/{item_id}``) instead of the
raw path (``/items/42``) to bound Prometheus cardinality. Unknown paths fall
back to the raw path, and the ``/metrics`` endpoint itself is excluded so
scraping never feeds back into the series it reads.
"""

from __future__ import annotations

import time

from opentelemetry import trace
from opentelemetry.propagate import extract
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from services.demo_api.observability.metrics import (
    http_client_errors_total,
    http_request_duration_seconds,
    http_requests_total,
    http_server_errors_total,
    in_flight_requests,
)

_tracer = trace.get_tracer("demo-api.http")


def _normalise_endpoint(scope: Scope) -> str:
    """Return the low-cardinality endpoint label for ``scope``."""
    route = scope.get("route")
    if route is not None:
        path = getattr(route, "path", None)
        if path:
            return str(path)
    router = scope.get("router")
    if router is not None:
        try:
            for r in getattr(router, "routes", []):
                match = getattr(r, "matches", None)
                if match is None:
                    continue
                result, _ = match(scope)
                if result:
                    path = getattr(r, "path", None)
                    if path:
                        return str(path)
        except Exception:  # pragma: no cover - best effort only
            pass
    return str(scope.get("path", "unknown"))


class ObservabilityMiddleware:
    """Record metrics and a server span for every HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method: str = str(scope.get("method", "UNKNOWN"))
        raw_path: str = str(scope.get("path", "unknown"))
        if raw_path == "/metrics":
            await self.app(scope, receive, send)
            return

        # Extract inbound W3C trace context so this service continues the
        # caller's trace instead of starting a disconnected one.
        headers = {
            name.decode("latin-1"): value.decode("latin-1")
            for name, value in scope.get("headers", [])
            if isinstance(name, bytes)
        }
        context = extract(headers)

        start = time.perf_counter()
        status_code = 500
        in_flight_requests.inc()
        try:
            with trace.use_span(
                _tracer.start_span(
                    f"{method} {raw_path}",
                    context=context,
                    kind=trace.SpanKind.SERVER,
                )
            ) as span:
                span.set_attribute("http.method", method)
                span.set_attribute("http.target", raw_path)

                async def send_with_status(message: Message) -> None:
                    nonlocal status_code
                    if message["type"] == "http.response.start":
                        status_code = int(message.get("status", 500))
                        span.set_attribute("http.status_code", status_code)
                    await send(message)

                try:
                    await self.app(scope, receive, send_with_status)
                except BaseException as exc:
                    span.record_exception(exc)
                    span.set_status(trace.Status(trace.StatusCode.ERROR))
                    raise
                if status_code >= 500:
                    span.set_status(trace.Status(trace.StatusCode.ERROR))
        finally:
            duration = time.perf_counter() - start
            in_flight_requests.dec()
            endpoint = _normalise_endpoint(scope)
            code = str(status_code)
            http_requests_total.labels(
                method=method, endpoint=endpoint, status_code=code
            ).inc()
            http_request_duration_seconds.labels(
                method=method, endpoint=endpoint, status_code=code
            ).observe(duration)
            if status_code >= 500:
                http_server_errors_total.labels(
                    method=method, endpoint=endpoint
                ).inc()
            elif status_code >= 400:
                http_client_errors_total.labels(
                    method=method, endpoint=endpoint
                ).inc()
