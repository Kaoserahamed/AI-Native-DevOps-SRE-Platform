"""Prometheus-format metrics endpoint.

``GET /metrics`` returns the current state of all registered Prometheus
counters and histograms in OpenMetrics text exposition format.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from services.demo_api.observability.metrics import render_metrics

router = APIRouter(tags=["observability"])


@router.get("/metrics")
async def metrics() -> Response:
    """Expose Prometheus metrics in OpenMetrics text format."""
    return Response(content=render_metrics(), media_type="text/plain; version=0.0.4")
