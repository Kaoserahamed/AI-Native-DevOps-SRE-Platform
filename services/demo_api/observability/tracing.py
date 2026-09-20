"""OpenTelemetry tracing initialization for the demo API.

Tracing is initialised once at startup and shut down gracefully via the
application lifespan. When the OTLP endpoint is not configured, no-op tracing
is used so the service runs standalone for local development.
"""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

logger = logging.getLogger("demo-api.tracing")


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
