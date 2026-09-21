"""Shared helpers for timed, traced dependency operations.

Every database or Redis call goes through one of these context managers so
metrics (count, latency, errors), traces (CLIENT spans) and the unified
``demo_api_dependency_failures_total`` series stay consistent. Operation
names are a closed vocabulary (``select``, ``insert``, ``delete``,
``health``, ``get``, ``set``, ``ping``) to bound cardinality.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import time

from services.demo_api.observability import metrics
from services.demo_api.observability.tracing import database_span, redis_span


@asynccontextmanager
async def timed_db_operation(operation: str) -> AsyncIterator[None]:
    """Record count, latency, errors and a span for one DB operation."""
    metrics.database_queries_total.labels(operation=operation).inc()
    start = time.perf_counter()
    try:
        async with database_span(operation):
            yield
    except Exception:
        metrics.demo_api_database_errors_total.labels(operation=operation).inc()
        metrics.demo_api_dependency_failures_total.labels(
            dependency="database", operation=operation
        ).inc()
        raise
    finally:
        metrics.demo_api_database_query_duration_seconds.labels(
            operation=operation
        ).observe(time.perf_counter() - start)


@asynccontextmanager
async def timed_redis_operation(operation: str) -> AsyncIterator[None]:
    """Record latency, errors and a span for one Redis operation."""
    start = time.perf_counter()
    try:
        async with redis_span(operation):
            yield
    except Exception:
        metrics.demo_api_redis_errors_total.labels(operation=operation).inc()
        metrics.demo_api_dependency_failures_total.labels(
            dependency="redis", operation=operation
        ).inc()
        raise
    finally:
        metrics.demo_api_redis_operation_duration_seconds.labels(
            operation=operation
        ).observe(time.perf_counter() - start)
