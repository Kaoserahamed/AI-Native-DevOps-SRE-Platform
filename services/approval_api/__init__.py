"""Approval workflow service for remediation governance.

Provides endpoints for human approval of remediation proposals with
expiry, identity verification, and audit trail.
"""

from __future__ import annotations

__all__ = ["create_app"]

from services.approval_api.app import create_app
