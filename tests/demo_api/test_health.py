"""API contract tests for health, readiness and metrics endpoints."""

from __future__ import annotations

from httpx import AsyncClient
import pytest

pytestmark = pytest.mark.contract


async def test_health_endpoint(sync_client: AsyncClient) -> None:
    """GET /health returns 200 with a timestamp."""
    response = await sync_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


async def test_readiness_endpoint(sync_client: AsyncClient) -> None:
    """GET /ready returns 200 when the fakes are healthy."""
    response = await sync_client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"] == {"database": True, "redis": True}


async def test_metrics_endpoint(sync_client: AsyncClient) -> None:
    """GET /metrics returns Prometheus text format."""
    response = await sync_client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    # The service info metric should be present
    assert "demo_api_info" in body


async def test_correlation_id_in_response_headers(sync_client: AsyncClient) -> None:
    """X-Request-ID header is present on responses."""
    response = await sync_client.get("/health")
    assert "x-request-id" in {k.lower() for k in response.headers}


async def test_custom_correlation_id_preserved(sync_client: AsyncClient) -> None:
    """A client-supplied X-Request-ID is echoed in the response."""
    response = await sync_client.get("/health", headers={"X-Request-ID": "test-correlation-123"})
    assert response.headers.get("x-request-id") == "test-correlation-123"
