"""OpenTelemetry tracing initialization for the demo API.

Tracing is initialised once at startup and shut down gracefully via the
application lifespan. When the OTLP endpoint is not configured, no-op tracing
is used so the service runs standalone for local development.

Resource attributes (``service.name``, ``service.version``,
``deployment.environment``) are consistent across every service by
convention (see ``docs/07-observability.md``): the middleware, the database
helpers and the Redis helpers below all reuse the tracer names declared
here, and propagation uses W3C ``traceparent`` over HTTP plus an explicit
carrier for queue jobs (documented in the collector README).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import SpanKind, Status, StatusCode

logger = logging.getLogger("demo-api.tracing")

RESOURCE_ATTRIBUTES: tuple[str, ...] = (
    "service.name",
    "service.version",
    "deployment.environment",
)


def init_tracing(
    app_name: str,
    app_version: str,
    app_env: str,
    otel_endpoint: str | None,
    enable_tracing: bool = True,
) -> TracerProvider | None:
    """Initialise the global tracer provider.

    Returns the provider so callers can shut it down, or ``None`` when tracing
    is disabled.
    """
    if not enable_tracing:
        logger.info("Tracing disabled by configuration")
        return None

    resource = Resource.create(
        {
            "service.name": app_name,
            "service.version": app_version,
            "deployment.environment": app_env,
        }
    )

    provider = TracerProvider(resource=resource)

    if otel_endpoint:
        exporter: OTLPSpanExporter | ConsoleSpanExporter = OTLPSpanExporter(
            endpoint=otel_endpoint, insecure=otel_endpoint.startswith("http://")
        )
    else:
        logger.warning("No OTLP endpoint configured; traces will be emitted to the console only")
        exporter = ConsoleSpanExporter()

    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    logger.info("Tracing initialised for service %s", app_name)
    return provider


def shutdown_tracing(provider: TracerProvider | None) -> None:
    """Force-flush and shut down the tracer provider."""
    if provider is None:
        return
    try:
        provider.force_flush(timeout_millis=3000)
    finally:
        provider.shutdown()
    logger.info("Tracing shut down")


def get_tracer(name: str = "demo-api") -> trace.Tracer:
    """Return a tracer bound to the global provider (no-op when disabled)."""
    return trace.get_tracer(name)


@asynccontextmanager
async def database_span(operation: str, **attributes: Any) -> AsyncIterator[trace.Span]:
    """Create a CLIENT span for a database operation.

    Wraps one logical query (``select``, ``insert``, ``delete``, health
    check) so database time is visible inside the parent HTTP span.
    """
    tracer = get_tracer("demo-api.database")
    with tracer.start_as_current_span(
        f"db.{operation}", kind=SpanKind.CLIENT
    ) as span:
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.operation", operation)
        for key, value in attributes.items():
            span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


@asynccontextmanager
async def redis_span(operation: str, **attributes: Any) -> AsyncIterator[trace.Span]:
    """Create a CLIENT span for a Redis operation (``get``, ``set``, ...)."""
    tracer = get_tracer("demo-api.redis")
    with tracer.start_as_current_span(
        f"redis.{operation}", kind=SpanKind.CLIENT
    ) as span:
        span.set_attribute("db.system", "redis")
        span.set_attribute("db.operation", operation)
        for key, value in attributes.items():
            span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
