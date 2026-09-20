"""Validation, invariant and safety tests for the versioned platform contracts.

These tests are the executable form of the contract promises: bounded evidence, evidence-grounded
diagnoses, a single-use approval bound to an action hash, append-only audit chaining, and an incident
state machine that cannot skip steps.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

import pytest
from pydantic import ValidationError

import packages.contracts as contracts
from packages.contracts import (
    ALLOWED_TRANSITIONS,
    AgentDecision,
    Alert,
    ApiError,
    Approval,
    AuditEvent,
    Evidence,
    Incident,
    IncidentStatus,
    RemediationProposal,
    can_transition,
)

pytestmark = pytest.mark.contract

PAYLOAD_FIXTURES: Final[tuple[tuple[str, str], ...]] = (
    ("alert", "Alert"),
    ("evidence", "Evidence"),
    ("incident", "Incident"),
    ("proposal", "RemediationProposal"),
    ("approval", "Approval"),
    ("decision", "AgentDecision"),
    ("audit", "AuditEvent"),
    ("api_error", "ApiError"),
)


@pytest.mark.parametrize(("fixture_name", "model_name"), PAYLOAD_FIXTURES)
def test_payload_round_trips(
    request: pytest.FixtureRequest, fixture_name: str, model_name: str
) -> None:
    """A canonical payload validates and survives a JSON round trip unchanged."""
    payload: dict[str, Any] = request.getfixturevalue(f"{fixture_name}_payload")
    model = getattr(contracts, model_name)

    instance = model.model_validate(payload)
    dumped = instance.model_dump(mode="json", exclude_computed_fields=True)

    assert model.model_validate(dumped) == instance


@pytest.mark.parametrize(("fixture_name", "model_name"), PAYLOAD_FIXTURES)
def test_schema_version_defaults_to_v1(
    request: pytest.FixtureRequest, fixture_name: str, model_name: str
) -> None:
    """Every payload carries the contract version, defaulted when a producer omits it."""
    payload: dict[str, Any] = request.getfixturevalue(f"{fixture_name}_payload")
    payload.pop("schema_version")
    model = getattr(contracts, model_name)

    assert model.model_validate(payload).schema_version == "v1"


@pytest.mark.parametrize(("fixture_name", "model_name"), PAYLOAD_FIXTURES)
def test_unknown_fields_are_rejected(
    request: pytest.FixtureRequest, fixture_name: str, model_name: str
) -> None:
    """``extra="forbid"`` keeps undocumented fields from silently gaining meaning."""
    payload: dict[str, Any] = request.getfixturevalue(f"{fixture_name}_payload")
    payload["unexpected_field"] = "value"
    model = getattr(contracts, model_name)

    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize(("fixture_name", "model_name"), PAYLOAD_FIXTURES)
def test_payloads_are_immutable(
    request: pytest.FixtureRequest, fixture_name: str, model_name: str
) -> None:
    """Frozen payloads cannot be mutated after validation, which protects the audit trail."""
    payload: dict[str, Any] = request.getfixturevalue(f"{fixture_name}_payload")
    model = getattr(contracts, model_name)
    instance = model.model_validate(payload)

    with pytest.raises(ValidationError):
        instance.__setattr__("schema_version", "v2")


def test_naive_timestamps_are_rejected(alert_payload: dict[str, Any]) -> None:
    """Timestamps must carry an explicit offset so ordering is unambiguous."""
    alert_payload["fired_at"] = "2026-09-20T10:00:00"

    with pytest.raises(ValidationError, match="timezone-aware"):
        Alert.model_validate(alert_payload)


def test_alert_rejects_malformed_labels(alert_payload: dict[str, Any]) -> None:
    """Label keys are constrained because labels are attacker-influenceable telemetry."""
    alert_payload["labels"] = {"Namespace": "demo"}

    with pytest.raises(ValidationError, match="label key"):
        Alert.model_validate(alert_payload)


def test_alert_rejects_too_many_labels(alert_payload: dict[str, Any]) -> None:
    """Label cardinality is bounded to protect metrics and prompts."""
    alert_payload["labels"] = {f"label_{index}": "x" for index in range(40)}

    with pytest.raises(ValidationError):
        Alert.model_validate(alert_payload)


def test_alert_rejects_resolution_before_firing(alert_payload: dict[str, Any]) -> None:
    """An alert cannot resolve before it fired."""
    alert_payload["resolved_at"] = "2026-09-20T09:00:00+00:00"

    with pytest.raises(ValidationError, match="resolved_at"):
        Alert.model_validate(alert_payload)


# ---------------------------------------------------------------------------
# Evidence stays bounded: the first line of defence for cost and for
# prompt-injection containment.
# ---------------------------------------------------------------------------


def test_evidence_window_must_be_bounded(evidence_payload: dict[str, Any]) -> None:
    """A six-hour ceiling keeps evidence retrieval from becoming a telemetry dump."""
    evidence_payload["window"] = {
        "start": "2026-09-20T00:00:00+00:00",
        "end": "2026-09-20T10:00:00+00:00",
    }

    with pytest.raises(ValidationError, match="window must not exceed"):
        Evidence.model_validate(evidence_payload)


def test_evidence_window_must_be_ordered(evidence_payload: dict[str, Any]) -> None:
    """An inverted window is a collector bug, not an empty result."""
    evidence_payload["window"] = {
        "start": "2026-09-20T10:00:00+00:00",
        "end": "2026-09-20T09:00:00+00:00",
    }

    with pytest.raises(ValidationError, match="later than window start"):
        Evidence.model_validate(evidence_payload)


def test_time_series_evidence_requires_a_window(evidence_payload: dict[str, Any]) -> None:
    """Metric and trace evidence without a window cannot be interpreted."""
    evidence_payload.pop("window")

    with pytest.raises(ValidationError, match="requires an observation window"):
        Evidence.model_validate(evidence_payload)


def test_evidence_payload_size_is_bounded(evidence_payload: dict[str, Any]) -> None:
    """Oversized payloads are rejected before they can reach a prompt."""
    evidence_payload["payload"] = {"blob": "x" * 20_000}

    with pytest.raises(ValidationError, match="payload must not exceed"):
        Evidence.model_validate(evidence_payload)


def test_evidence_requires_excerpt_or_payload(evidence_payload: dict[str, Any]) -> None:
    """Empty evidence is meaningless evidence."""
    evidence_payload.pop("payload")
    evidence_payload.pop("excerpt")

    with pytest.raises(ValidationError, match="excerpt or a structured payload"):
        Evidence.model_validate(evidence_payload)


def test_evidence_reports_its_size(evidence_payload: dict[str, Any]) -> None:
    """Agents are charged for the bytes they receive, so the size must be derivable."""
    evidence = Evidence.model_validate(evidence_payload)

    assert evidence.evidence_bytes == evidence.size_bytes + len(evidence.excerpt or "")
    assert 0 < evidence.size_bytes <= 16_384


# ---------------------------------------------------------------------------
# Incident lifecycle invariants
# ---------------------------------------------------------------------------


def resolved_incident_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a valid resolved incident derived from the base payload."""
    resolved = dict(payload)
    resolved.update(
        {
            "status": "resolved",
            "acknowledged_at": "2026-09-20T10:05:00+00:00",
            "resolved_at": "2026-09-20T10:20:00+00:00",
            "evidence_ids": ["EVD-2026-0001"],
            "resolution_summary": "Rolled back the previous revision; error ratio returned to baseline.",
        }
    )
    return resolved


def test_acknowledged_incident_requires_a_timestamp(incident_payload: dict[str, Any]) -> None:
    """A status without its timestamp means the lifecycle was bypassed."""
    incident_payload["status"] = "acknowledged"

    with pytest.raises(ValidationError, match="requires acknowledged_at"):
        Incident.model_validate(incident_payload)


def test_acknowledged_incident_requires_evidence(incident_payload: dict[str, Any]) -> None:
    """Nobody acknowledges an incident without having looked at something."""
    incident_payload.update(
        {"status": "acknowledged", "acknowledged_at": "2026-09-20T10:05:00+00:00"}
    )

    with pytest.raises(ValidationError, match="at least one evidence item"):
        Incident.model_validate(incident_payload)


def test_resolved_incident_requires_a_summary(incident_payload: dict[str, Any]) -> None:
    """Resolution without a written summary cannot be reviewed or learned from."""
    payload = resolved_incident_payload(incident_payload)
    payload.pop("resolution_summary")

    with pytest.raises(ValidationError, match="requires a resolution_summary"):
        Incident.model_validate(payload)


def test_resolution_summary_is_rejected_before_resolution(incident_payload: dict[str, Any]) -> None:
    """State and narrative must agree."""
    incident_payload["resolution_summary"] = "Looks fine now."

    with pytest.raises(ValidationError, match="once the incident is resolved"):
        Incident.model_validate(incident_payload)


def test_closed_incident_may_carry_post_incident_notes(incident_payload: dict[str, Any]) -> None:
    """Post-incident notes are only meaningful after closure."""
    payload = resolved_incident_payload(incident_payload)
    payload.update(
        {
            "status": "closed",
            "closed_at": "2026-09-20T11:00:00+00:00",
            "post_incident_notes": "Add a canary stage before promoting the error-rate objective.",
        }
    )

    incident = Incident.model_validate(payload)

    assert incident.status is IncidentStatus.CLOSED
    assert incident.post_incident_notes is not None


def test_post_incident_notes_require_closure(incident_payload: dict[str, Any]) -> None:
    """Notes on an open incident would be lost or misleading."""
    incident_payload["post_incident_notes"] = "Premature note."

    with pytest.raises(ValidationError, match="once the incident is closed"):
        Incident.model_validate(incident_payload)


def test_reopened_incident_must_clear_resolution(incident_payload: dict[str, Any]) -> None:
    """A reopened incident is unresolved again, which keeps the SLO maths honest."""
    payload = resolved_incident_payload(incident_payload)
    payload["status"] = "reopened"

    with pytest.raises(ValidationError, match="clear resolved_at"):
        Incident.model_validate(payload)


def test_mitigating_incident_requires_a_proposal(incident_payload: dict[str, Any]) -> None:
    """Mitigation means an action exists, so it must be referenced."""
    incident_payload.update(
        {
            "status": "mitigating",
            "acknowledged_at": "2026-09-20T10:05:00+00:00",
            "evidence_ids": ["EVD-2026-0001"],
        }
    )

    with pytest.raises(ValidationError, match="proposal or an approval"):
        Incident.model_validate(incident_payload)


def test_cause_must_cite_attached_evidence(incident_payload: dict[str, Any]) -> None:
    """Uncited or external causes are how a hallucination becomes an incident record."""
    incident_payload.update(
        {
            "status": "investigating",
            "acknowledged_at": "2026-09-20T10:05:00+00:00",
            "evidence_ids": ["EVD-2026-0001"],
            "suspected_causes": [
                {
                    "category": "deployment_regression",
                    "description": "The rollout introduced a regression.",
                    "confidence": 0.6,
                    "evidence_ids": ["EVD-2026-9999"],
                }
            ],
            "confidence": 0.6,
        }
    )

    with pytest.raises(ValidationError, match="evidence not attached"):
        Incident.model_validate(incident_payload)


def test_confidence_requires_suspected_causes(incident_payload: dict[str, Any]) -> None:
    """A confidence value without a cause is meaningless."""
    incident_payload["confidence"] = 0.4

    with pytest.raises(ValidationError, match="alongside suspected causes"):
        Incident.model_validate(incident_payload)


def test_timeline_must_be_non_decreasing(incident_payload: dict[str, Any]) -> None:
    """Ordered timestamps are what make MTTA and MTTR measurements trustworthy."""
    incident_payload["detected_at"] = "2026-09-20T10:30:00+00:00"

    with pytest.raises(ValidationError, match="opened_at must not be earlier"):
        Incident.model_validate(incident_payload)


def test_closed_is_terminal_and_open_may_resolve() -> None:
    """The transition table is a safety property and must stay conservative."""
    assert not can_transition(IncidentStatus.CLOSED, IncidentStatus.OPEN)
    assert can_transition(IncidentStatus.OPEN, IncidentStatus.RESOLVED)
    assert can_transition(IncidentStatus.RESOLVED, IncidentStatus.REOPENED)
    assert not can_transition(IncidentStatus.OPEN, IncidentStatus.CLOSED)


def test_transition_table_covers_every_status() -> None:
    """Every status has an explicit entry, so a new status cannot silently allow nothing."""
    assert set(ALLOWED_TRANSITIONS) == set(IncidentStatus)
    for targets in ALLOWED_TRANSITIONS.values():
        assert targets <= set(IncidentStatus)


# ---------------------------------------------------------------------------
# Agent grounding and the "insufficient evidence" escape hatch
# ---------------------------------------------------------------------------


def test_agent_decision_must_cite_provided_evidence(decision_payload: dict[str, Any]) -> None:
    """A citation of evidence the agent never received is a fabricated citation."""
    decision_payload["citations"] = [{"evidence_id": "EVD-2026-9999", "quote": "invented"}]

    with pytest.raises(ValidationError, match="evidence that was not provided"):
        AgentDecision.model_validate(decision_payload)


def test_agent_decision_requires_citations(decision_payload: dict[str, Any]) -> None:
    """A diagnosis without citations is an opinion, not a diagnosis."""
    decision_payload["citations"] = []

    with pytest.raises(ValidationError, match="requires at least one citation"):
        AgentDecision.model_validate(decision_payload)


def test_agent_decision_requires_evidence(decision_payload: dict[str, Any]) -> None:
    """No evidence means the agent must use the insufficient-evidence outcome instead."""
    decision_payload["evidence_ids"] = []
    decision_payload["citations"] = []

    with pytest.raises(ValidationError, match="requires at least one evidence item"):
        AgentDecision.model_validate(decision_payload)


def test_insufficient_evidence_is_a_safe_outcome(decision_payload: dict[str, Any]) -> None:
    """The honest outcome is allowed: low confidence, no citations, no recommended action."""
    decision_payload.update(
        {
            "diagnosis": "insufficient_evidence",
            "confidence": 0.2,
            "evidence_ids": [],
            "citations": [],
            "recommended_action": None,
            "uncertainty": "Logs for the window were unavailable.",
        }
    )

    decision = AgentDecision.model_validate(decision_payload)

    assert decision.confidence == 0.2
    assert decision.recommended_action is None


def test_insufficient_evidence_must_not_be_confident(decision_payload: dict[str, Any]) -> None:
    """Claiming certainty without evidence is the failure mode the platform exists to prevent."""
    decision_payload.update(
        {"diagnosis": "insufficient_evidence", "confidence": 0.9, "recommended_action": None}
    )

    with pytest.raises(ValidationError, match="must not claim high confidence"):
        AgentDecision.model_validate(decision_payload)


def test_insufficient_evidence_must_not_recommend_an_action(
    decision_payload: dict[str, Any],
) -> None:
    """An action without evidence is exactly what the approval gate must never see."""
    decision_payload.update({"diagnosis": "insufficient_evidence", "confidence": 0.2})

    with pytest.raises(ValidationError, match="must not recommend an action"):
        AgentDecision.model_validate(decision_payload)


def test_no_action_required_must_not_recommend_an_action(decision_payload: dict[str, Any]) -> None:
    """A diagnosis of "nothing to do" cannot also carry an action."""
    decision_payload["diagnosis"] = "no_action_required"

    with pytest.raises(ValidationError, match="must not recommend an action"):
        AgentDecision.model_validate(decision_payload)


def test_diagnosis_requires_a_recommended_action(decision_payload: dict[str, Any]) -> None:
    """A real diagnosis must produce a proposal category for the remediation agent."""
    decision_payload["recommended_action"] = None

    with pytest.raises(ValidationError, match="must recommend a remediation category"):
        AgentDecision.model_validate(decision_payload)
