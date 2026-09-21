"""Incident Lifecycle API service.

Provides RESTful endpoints for creating, updating, and managing incidents
with evidence attachment and state transitions.
"""

from __future__ import annotations

__all__ = ["create_app"]

from services.incident_api.app import create_app
