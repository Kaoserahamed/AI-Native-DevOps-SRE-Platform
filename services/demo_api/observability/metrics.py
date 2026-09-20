"""Prometheus metrics for the demo API.

Metrics are exposed in OpenMetrics text format on ``GET /metrics``. The
``prometheus_client`` library provides a process-wide registry; the application
adds HTTP-level counters and timers on top of it.
"""

from __future__ import annotations

from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)

# HTTP request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
)

# In-flight request gauge
in_flight_requests = Gauge(
    "in_flight_requests",
    "Number of requests currently being processed",
)

# Application-level metrics
items_created_total = Counter(
    "demo_api_items_created_total",
    "Total number of items created through the API",
)

items_deleted_total = Counter(
    "demo_api_items_deleted_total",
    "Total number of items deleted through the API",
)

database_queries_total = Counter(
    "demo_api_database_queries_total",
    "Total number of database queries executed",
    ["operation"],
)

redis_hits_total = Counter(
    "demo_api_redis_hits_total",
    "Number of Redis cache hits",
)

redis_misses_total = Counter(
    "demo_api_redis_misses_total",
    "Number of Redis cache misses",
)

# Service info
service_info = Info("demo_api", "Demo API service metadata")

# Failure injection metric
failures_injected_total = Counter(
    "demo_api_failures_injected_total",
    "Total number of failures injected by the test-only failure mode",
    ["failure_mode"],
)


def setup_metrics(app_name: str, app_version: str, app_env: str) -> Info:
    """Set the service info metric and return it for reference."""
    service_info.info({"name": app_name, "version": app_version, "environment": app_env})
    return service_info


def render_metrics(registry: CollectorRegistry | None = None) -> str:
    """Return the latest metrics in OpenMetrics text format."""
    return generate_latest(registry or REGISTRY).decode("utf-8")
