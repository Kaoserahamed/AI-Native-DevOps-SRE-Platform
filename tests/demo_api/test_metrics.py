"""Tests for the Prometheus metric definitions.

The exposition format is the contract Prometheus scrapes, so these tests pin what is easy to get subtly
wrong: the histogram's declared bucket bounds, the service info metric that identifies the running
version, and the fact that the client owns the ``+Inf`` bucket.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from services.demo_api.observability.metrics import (
    http_request_duration_seconds,
    render_metrics,
    service_info,
    setup_metrics,
)

pytestmark = pytest.mark.unit


def test_declared_bucket_bounds_are_finite_and_ascending() -> None:
    """Only finite, ascending bounds are declared; ``prometheus_client`` appends the ``+Inf`` bucket.

    Prometheus estimates latency quantiles from the bucket boundaries, so a non-ascending or
    hand-declared ``+Inf`` boundary silently skews ``histogram_quantile`` results.
    """
    bounds = [float(bound) for bound in http_request_duration_seconds._upper_bounds]

    assert bounds[-1] == math.inf
    declared = bounds[:-1]
    assert all(math.isfinite(bound) for bound in declared)
    assert declared == sorted(declared)


def test_histogram_exposes_exactly_one_infinity_bucket_per_series() -> None:
    """Every observed series ends in exactly one ``+Inf`` bucket, as Prometheus requires."""
    histogram: Any = http_request_duration_seconds.labels(
        method="GET", endpoint="/health", status_code="200"
    )
    histogram.observe(0.004)

    exposition = render_metrics()
    bucket_lines = [
        line
        for line in exposition.splitlines()
        if line.startswith("http_request_duration_seconds_bucket{") and 'endpoint="/health"' in line
    ]
    infinity_lines = [line for line in bucket_lines if 'le="+Inf"' in line]

    assert len(infinity_lines) == 1
    assert bucket_lines[-1] == infinity_lines[0]


def test_setup_metrics_records_service_identity() -> None:
    """The info metric exposes the name, version and environment Prometheus joins on."""
    setup_metrics(app_name="demo-api-test", app_version="9.9.9", app_env="development")

    exposition = render_metrics()

    assert "demo_api_info{" in exposition
    assert 'name="demo-api-test"' in exposition
    assert 'version="9.9.9"' in exposition
    assert 'environment="development"' in exposition
    assert service_info is not None
