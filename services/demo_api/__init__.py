"""Demo API service: an observable data-plane workload.

This service is the reference target workload for the platform. It produces
real telemetry (structured logs, Prometheus metrics, OpenTelemetry traces)
and persists state in PostgreSQL with a Redis cache, so the control plane has
something realistic to observe, diagnose and remediate.
"""

from __future__ import annotations

__all__ = ["__version__"]
__version__ = "0.1.0"
