"""Health and readiness endpoints.

``GET /health`` is a liveness probe: it answers whether the process is
running. ``GET /ready`` is a readiness probe: it checks that PostgreSQL and
Redis are reachable before traffic is routed to the pod.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from services.demo_api.db.session import get_session_factory
from services.demo_api.redis_client import get_redis_client

router = APIRouter(tags=["health"])


def _now() -> str:
    """Return the current UTC timestamp as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


@router.get("/health")
async def health() -> dict[str, Any]:
    """Liveness probe: the process is running."""
    return {"status": "ok", "timestamp": _now()}


async def _check_readiness() -> dict[str, Any]:
    """Check each downstream dependency and return a readiness summary."""
    checks: dict[str, bool] = {}

    # Database check
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # Redis check
    try:
        client = get_redis_client()
        await client.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    ready = all(checks.values())
    return {
        "status": "ready" if ready else "not_ready",
        "timestamp": _now(),
        "checks": checks,
    }


@router.get("/ready")
async def readiness() -> dict[str, Any]:
    """Readiness probe: verify PostgreSQL and Redis are reachable."""
    result = await _check_readiness()
    if result["status"] != "ready":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=result)
    return result
