"""Tests for incident analyzer using fake LLM provider."""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone

from packages.contracts.common import Confidence, Severity
from packages.contracts.incidents import CauseCategory, Incident, IncidentStatus
from packages.llm.fake import FakeLlmProvider, ScriptedReply
from services.incident_agent.analyzer import AnalysisResult, IncidentAnalyzer, analyze_incident


def _result_to_json(result: AnalysisResult) -> str:
    """Convert AnalysisResult to JSON string for fake provider."""
    return json.dumps(result.model_dump())


@pytest.fixture
def fake_llm() -> FakeLlmProvider:
    """Return a fake LLM provider for testing."""
    analysis = AnalysisResult(
        category=CauseCategory.DEPLOYMENT_REGRESSION,
        description="High error rate after deployment",
        confidence=0.85,
        reasoning="Error rate increased from 0.1% to 5% immediately after deployment",
        insufficient_evidence=False,
    )
    return FakeLlmProvider(
        script=[ScriptedReply(content=_result_to_json(analysis))],
    )


@pytest.fixture
def sample_incident() -> Incident:
    """Return a sample incident for testing."""
    now = datetime.now(timezone.utc)
    return Incident(
        incident_id="inc-001",
        title="High 5xx rate in demo-api",
        severity=Severity.HIGH,
        service="demo-api",
        status=IncidentStatus.OPEN,
        detected_at=now,
        opened_at=now,
        triggering_alert_ids=["alert-001"],
    )


@pytest.mark.unit
async def test_analyzer_with_sufficient_evidence(fake_llm: FakeLlmProvider) -> None:
    """Test analyzer produces a diagnosis when evidence is sufficient."""
    analyzer = IncidentAnalyzer(fake_llm)

    evidence = {
        "log-001": {"message": "Error connecting to database", "count": 150},
        "metric-001": {"error_rate": 5.2, "previous_rate": 0.1},
    }

    suspected_cause, confidence = await analyzer.analyze(
        incident_id="inc-001",
        alert_description="5xx rate exceeded 5%",
        evidence=evidence,
        severity=Severity.HIGH,
    )

    assert suspected_cause is not None
    assert suspected_cause.category == CauseCategory.DEPLOYMENT_REGRESSION
    assert suspected_cause.description == "High error rate after deployment"
    assert confidence == 0.85
    assert len(suspected_cause.evidence_ids) == 2


@pytest.mark.unit
async def test_analyzer_with_insufficient_evidence(fake_llm: FakeLlmProvider) -> None:
    """Test analyzer returns None when evidence is insufficient."""
    # Create response indicating insufficient evidence
    analysis = AnalysisResult(
        category=CauseCategory.UNKNOWN,
        description="Cannot determine cause",
        confidence=0.0,
        reasoning="Not enough data to make assessment",
        insufficient_evidence=True,
    )
    fake_llm_insufficient = FakeLlmProvider(
        script=[ScriptedReply(content=_result_to_json(analysis))],
    )

    analyzer = IncidentAnalyzer(fake_llm_insufficient)

    evidence = {"log-001": {"message": "Single error log"}}

    suspected_cause, confidence = await analyzer.analyze(
        incident_id="inc-002",
        alert_description="Alert triggered",
        evidence=evidence,
        severity=Severity.LOW,
    )

    assert suspected_cause is None
    assert confidence == 0.0


@pytest.mark.unit
async def test_analyze_incident_updates_status(
    sample_incident: Incident, fake_llm: FakeLlmProvider
) -> None:
    """Test analyze_incident updates incident with analysis results."""
    evidence = {
        "log-001": {"message": "Deployment failed", "timestamp": "2024-01-01T00:00:00Z"},
        "metric-001": {"error_rate": 8.5},
    }

    updated_incident = await analyze_incident(sample_incident, evidence, fake_llm)

    assert updated_incident.status == IncidentStatus.INVESTIGATING
    assert len(updated_incident.suspected_causes) == 1
    assert updated_incident.confidence is not None
    assert updated_incident.confidence > 0.5
    assert updated_incident.suspected_causes[0].category == CauseCategory.DEPLOYMENT_REGRESSION


@pytest.mark.unit
async def test_analyze_incident_handles_no_diagnosis(
    sample_incident: Incident,
) -> None:
    """Test analyze_incident when no diagnosis can be made."""
    analysis = AnalysisResult(
        category=CauseCategory.UNKNOWN,
        description="No analysis",
        confidence=0.0,
        reasoning="No evidence",
        insufficient_evidence=True,
    )
    fake_llm_no_diag = FakeLlmProvider(
        script=[ScriptedReply(content=_result_to_json(analysis))],
    )

    evidence = {}

    updated_incident = await analyze_incident(sample_incident, evidence, fake_llm_no_diag)

    # Status should remain unchanged when no diagnosis is made
    assert updated_incident.status == IncidentStatus.OPEN
    assert len(updated_incident.suspected_causes) == 0
    assert updated_incident.confidence is None
