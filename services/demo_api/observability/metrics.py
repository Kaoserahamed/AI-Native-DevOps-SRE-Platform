"""Prometheus metrics for the demo API.

Metrics are exposed in OpenMetrics text format on ``GET /metrics``. The
``prometheus_client`` library provides a process-wide registry; the application
adds HTTP-level counters and timers on top of it.

Metric naming follows ``docs/07-observability.md``:

- HTTP server metrics (``http_*``) use the Prometheus community convention
  (``method``, ``endpoint``, ``status_code`` labels). They are recorded by
  the observability middleware, not by individual routes, so every response
  — including unhandled errors — is counted exactly once.
- Application metrics are prefixed ``demo_api_`` and are recording-rule
  friendly.
- Platform metrics (queue, worker, agent, PR, remediation) are declared here
  with the label sets the recording rules and dashboards expect, so later
  phases (worker, agents, GitHub automation) can record against a stable
  contract without renaming series. Until those components exist they stay
  at zero, which keeps the alert and SLO rules stated without firing.
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


def _latency_buckets() -> tuple[float, ...]:
    """Return the shared latency bucket bounds for duration histograms."""
    return (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


# HTTP request metrics (recorded by the observability middleware)
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint", "status_code"],
    buckets=(*_latency_buckets(), float("inf")),
)

http_server_errors_total = Counter(
    "http_server_errors_total",
    "Total number of HTTP responses with a 5xx status code",
    ["method", "endpoint"],
)

http_client_errors_total = Counter(
    "http_client_errors_total",
    "Total number of HTTP responses with a 4xx status code",
    ["method", "endpoint"],
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

demo_api_database_errors_total = Counter(
    "demo_api_database_errors_total",
    "Total number of failed database operations",
    ["operation"],
)

demo_api_database_query_duration_seconds = Histogram(
    "demo_api_database_query_duration_seconds",
    "Database query latency in seconds",
    ["operation"],
    buckets=(*_latency_buckets(), float("inf")),
)

redis_hits_total = Counter(
    "demo_api_redis_hits_total",
    "Number of Redis cache hits",
)

redis_misses_total = Counter(
    "demo_api_redis_misses_total",
    "Number of Redis cache misses",
)

demo_api_redis_errors_total = Counter(
    "demo_api_redis_errors_total",
    "Total number of failed Redis operations",
    ["operation"],
)

demo_api_redis_operation_duration_seconds = Histogram(
    "demo_api_redis_operation_duration_seconds",
    "Redis operation latency in seconds",
    ["operation"],
    buckets=(*_latency_buckets(), float("inf")),
)

demo_api_dependency_failures_total = Counter(
    "demo_api_dependency_failures_total",
    "Total number of downstream dependency failures (database or cache)",
    ["dependency", "operation"],
)

# Service info
service_info = Info("demo_api", "Demo API service metadata")

# Failure injection metric
failures_injected_total = Counter(
    "demo_api_failures_injected_total",
    "Total number of failures injected by the test-only failure mode",
    ["failure_mode"],
)

# --- Platform metrics (Phase 6 Task 6.1 contract) ---
# Declared here so recording rules, alerts and dashboards have stable series
# names and label sets before the worker/agent/GitHub phases land. Until those
# components exist the series stay at zero, which is the documented "no data
# yet" state (see docs/07-observability.md).

# Queue depth
work_queue_depth = Gauge(
    "work_queue_depth",
    "Number of jobs waiting in the work queue",
    ["queue"],
)

# Worker processing time
worker_job_duration_seconds = Histogram(
    "worker_job_duration_seconds",
    "Worker job processing time in seconds",
    ["queue", "job_type", "status"],
    buckets=(*_latency_buckets(), float("inf")),
)

worker_jobs_total = Counter(
    "worker_jobs_total",
    "Total number of worker jobs processed",
    ["queue", "job_type", "status"],
)

# Agent execution metrics
agent_executions_total = Counter(
    "agent_executions_total",
    "Total number of AI agent executions",
    ["agent", "status"],
)

agent_execution_duration_seconds = Histogram(
    "agent_execution_duration_seconds",
    "AI agent execution latency in seconds",
    ["agent"],
    buckets=(*_latency_buckets(), float("inf")),
)

agent_errors_total = Counter(
    "agent_errors_total",
    "Total number of failed AI agent executions",
    ["agent", "error_type"],
)

# PR creation outcomes (GitHub automation phase)
github_prs_total = Counter(
    "github_prs_total",
    "Total number of remediation pull requests opened",
    ["repository", "status"],
)

# Remediation approval outcomes (approval workflow phase)
remediation_approvals_total = Counter(
    "remediation_approvals_total",
    "Total number of remediation approval decisions",
    ["decision"],
)


def setup_metrics(app_name: str, app_version: str, app_env: str) -> Info:
    """Set the service info metric and return it for reference."""
    service_info.info({"name": app_name, "version": app_version, "environment": app_env})
    return service_info


def render_metrics(registry: CollectorRegistry | None = None) -> str:
    """Return the latest metrics in OpenMetrics text format."""
    return generate_latest(registry or REGISTRY).decode("utf-8")
