"""Deterministic payload fixtures for the contract test tier.

Fixtures are plain dictionaries so a test can mutate one field and assert the failure. Nothing here
touches the network, the clock or the file system: timestamps are fixed, which keeps the contract tests
reproducible and the exported schema snapshots stable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from packages.contracts.remediation import RemediationProposal

NOW = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
EVIDENCE_ID = "EVD-2026-0001"
EVIDENCE_ID_2 = "EVD-2026-0002"
INCIDENT_ID = "INC-2026-0001"
PROPOSAL_ID = "PRO-2026-0001"
APPROVAL_ID = "APR-2026-0001"
DECISION_ID = "DEC-2026-0001"
AUDIT_ID = "AUD-2026-0001"
CORRELATION_ID = "b6f1c0de-0001-4a11-9f6e-0123456789ab"
COMMIT_SHA = "4a1b2c3d4e5f60718293a4b5c6d7e8f901234567"


@pytest.fixture
def now() -> datetime:
    """Fixed reference time for deterministic payloads."""
    return NOW


@pytest.fixture
def service_payload() -> dict[str, Any]:
    """Reference to the demo workload under observation."""
    return {
        "name": "demo-api",
        "environment": "staging",
        "namespace": "demo",
        "revision": COMMIT_SHA,
    }


@pytest.fixture
def alert_payload(service_payload: dict[str, Any]) -> dict[str, Any]:
    """A normalized alert that triggers an incident."""
    return {
        "schema_version": "v1",
        "alert_id": "ALT-2026-0001",
        "fingerprint": "demo-api-high-error-rate",
        "name": "high_error_rate",
        "severity": "sev2",
        "service": service_payload,
        "source": "prometheus",
        "summary": "5xx ratio above 5 percent for 10 minutes",
        "description": "Error rate jumped immediately after a deployment.",
        "fired_at": NOW.isoformat(),
        "labels": {"namespace": "demo", "service": "demo-api"},
        "runbook_url": "https://example.test/runbooks/high-5xx",
        "slo": "demo-api-availability",
        "correlation_id": CORRELATION_ID,
    }


@pytest.fixture
def evidence_payload(service_payload: dict[str, Any]) -> dict[str, Any]:
    """Bounded metric evidence with an observation window."""
    return {
        "schema_version": "v1",
        "evidence_id": EVIDENCE_ID,
        "kind": "metric_series",
        "collector": "prometheus",
        "collected_at": NOW.isoformat(),
        "summary": "demo_api_http_5xx_ratio rose from 0.004 to 0.19 after 09:52",
        "service": service_payload,
        "window": {
            "start": (NOW - timedelta(minutes=30)).isoformat(),
            "end": NOW.isoformat(),
        },
        "excerpt": "5xx ratio 0.19 (baseline 0.004) for 8 minutes",
        "payload": {
            "query": "sum(rate(demo_api_http_requests_total{status=~'5..'}[5m]))",
            "points": [0.004, 0.19],
        },
        "labels": {"namespace": "demo"},
        "redacted": True,
        "incident_id": INCIDENT_ID,
        "correlation_id": CORRELATION_ID,
    }


@pytest.fixture
def incident_payload(service_payload: dict[str, Any]) -> dict[str, Any]:
    """A freshly opened incident."""
    return {
        "schema_version": "v1",
        "incident_id": INCIDENT_ID,
        "title": "demo-api error rate elevated after deployment",
        "severity": "sev2",
        "service": service_payload,
        "status": "open",
        "detected_at": (NOW - timedelta(minutes=8)).isoformat(),
        "opened_at": NOW.isoformat(),
        "triggering_alert_ids": ["ALT-2026-0001"],
        "correlation_id": CORRELATION_ID,
    }


@pytest.fixture
def proposal_payload() -> dict[str, Any]:
    """A restart/rollout proposal for the staging workload."""
    return {
        "schema_version": "v1",
        "proposal_id": PROPOSAL_ID,
        "incident_id": INCIDENT_ID,
        "category": "restart_or_rollout",
        "target": {
            "environment": "staging",
            "namespace": "demo",
            "workload": "demo-api",
            "resource_kind": "deployment",
            "revision": COMMIT_SHA,
        },
        "rationale": "Errors started within two minutes of the rollout and stop after a rollback.",
        "evidence_ids": [EVIDENCE_ID],
        "expected_impact": "Error ratio returns to the pre-deployment baseline within five minutes.",
        "blast_radius": "workload",
        "rollback_plan": "Re-apply the previous revision from the deployment history.",
        "confidence": 0.62,
        "required_permissions": ["deployments:rollout-restart"],
        "risk": "medium",
        "parameters": {"maxUnavailable": "0"},
        "created_at": NOW.isoformat(),
    }


@pytest.fixture
def approval_payload(proposal_payload: dict[str, Any]) -> dict[str, Any]:
    """An approved, unexpired decision bound to the proposal's action hash."""
    action_hash = RemediationProposal.model_validate(proposal_payload).action_hash
    return {
        "schema_version": "v1",
        "approval_id": APPROVAL_ID,
        "incident_id": INCIDENT_ID,
        "proposal_id": PROPOSAL_ID,
        "action_hash": action_hash,
        "approver": {"actor_type": "human", "identity": "oncall.engineer@example.test"},
        "decision": "approved",
        "comment": "Approved on the incident bridge; rollback plan reviewed.",
        "decided_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(minutes=30)).isoformat(),
        "correlation_id": CORRELATION_ID,
    }


@pytest.fixture
def decision_payload() -> dict[str, Any]:
    """A grounded, evidence-backed diagnosis."""
    return {
        "schema_version": "v1",
        "decision_id": DECISION_ID,
        "run_id": "RUN-2026-0001",
        "incident_id": INCIDENT_ID,
        "agent_type": "incident_agent",
        "agent_version": "0.1.0",
        "prompt_version": "incident-analysis/v3",
        "provider": "openai_compatible",
        "model": "gpt-5-mini",
        "created_at": NOW.isoformat(),
        "diagnosis": "deployment_regression",
        "summary": "Error rate rose immediately after the latest deployment.",
        "confidence": 0.62,
        "evidence_ids": [EVIDENCE_ID, EVIDENCE_ID_2],
        "citations": [
            {"evidence_id": EVIDENCE_ID, "quote": "5xx ratio 0.19 (baseline 0.004) for 8 minutes"},
            {
                "evidence_id": EVIDENCE_ID_2,
                "quote": "deployment demo-api revision 4a1b2c3 finished at 09:52",
                "note": "Correlates the degradation with the rollout.",
            },
        ],
        "uncertainty": "Only one deployment is in the window; a dependency fault is not fully excluded.",
        "recommended_action": "restart_or_rollout",
        "usage": {
            "prompt_tokens": 3200,
            "completion_tokens": 410,
            "cost_usd": 0.0121,
            "latency_ms": 8400,
            "model_calls": 1,
            "tool_calls": 4,
            "iterations": 2,
            "evidence_bytes": 4096,
        },
        "correlation_id": CORRELATION_ID,
    }


@pytest.fixture
def audit_payload() -> dict[str, Any]:
    """An audit event that starts a chain."""
    return {
        "schema_version": "v1",
        "event_id": AUDIT_ID,
        "occurred_at": NOW.isoformat(),
        "actor": {
            "actor_type": "agent",
            "actor_id": "incident_agent@0.1.0",
            "on_behalf_of": "oncall.engineer@example.test",
        },
        "event_type": "agent_invoked",
        "subject": INCIDENT_ID,
        "result": "succeeded",
        "correlation_id": CORRELATION_ID,
        "incident_id": INCIDENT_ID,
        "tool": "prometheus_query",
        "before": {"status": "investigating"},
        "after": {"status": "investigating", "evidence_count": 2},
        "attributes": {"prompt_version": "incident-analysis/v3"},
        "previous_digest": None,
    }


@pytest.fixture
def api_error_payload() -> dict[str, Any]:
    """A retryable server-side error response."""
    return {
        "schema_version": "v1",
        "error_code": "database_unavailable",
        "message": "The incident store is temporarily unavailable.",
        "status_code": 503,
        "correlation_id": CORRELATION_ID,
        "retryable": True,
        "details": [{"reason": "connection pool exhausted", "code": "pool_exhausted"}],
    }
