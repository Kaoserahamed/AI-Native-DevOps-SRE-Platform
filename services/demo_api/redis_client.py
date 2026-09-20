"""Async Redis client wrapper for caching and health checks."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("demo-api.redis")

# ``redis.asyncio.Redis`` is untyped upstream, so the module keeps the client as
# ``Any`` to stay compatible with strict mypy without per-line ignores.
_client: Any | None = None


def set_redis_client(client: Any) -> None:
    """Inject the Redis client created at application startup."""
    global _client
    _client = client


def get_redis_client() -> Any:
    """Return the active Redis client."""
    if _client is None:
        raise RuntimeError("Redis client has not been initialised")
    return _client


async def check_redis_health() -> bool:
    """Return ``True`` when Redis responds to a PING."""
    try:
        client = get_redis_client()
        pong = await client.ping()
        return bool(pong)
    except Exception as exc:
        logger.error("Redis health check failed: %s", exc)
        return False


async def get_cache(key: str) -> str | None:
    """Fetch a cached value by key, recording a hit/miss metric."""
    from services.demo_api.observability.metrics import redis_hits_total, redis_misses_total

    client = get_redis_client()
    value = await client.get(key)
    if value is not None:
        redis_hits_total.inc()
        return value.decode("utf-8") if isinstance(value, bytes) else value
    redis_misses_total.inc()
    return None


async def set_cache(key: str, value: str, ttl: int = 300) -> None:
    """Cache a value with an optional TTL (in seconds)."""
    client = get_redis_client()
    await client.setex(key, ttl, value)
