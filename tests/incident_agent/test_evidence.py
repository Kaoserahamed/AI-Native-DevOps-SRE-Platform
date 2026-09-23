"""Tests for evidence retrieval layer."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.incident_agent.evidence import (
    Evidence,
    EvidenceConstraints,
    EvidenceRetriever,
    retrieve_incident_evidence,
)


@pytest.fixture
def retriever() -> EvidenceRetriever:
    """Return an evidence retriever with default constraints."""
    return EvidenceRetriever()


@pytest.fixture
def custom_retriever() -> EvidenceRetriever:
    """Return an evidence retriever with custom constraints."""
    constraints = EvidenceConstraints(
        time_window_minutes=15,
        max_log_entries=50,
        max_metric_points=25,
        max_trace_samples=10,
    )
    return EvidenceRetriever(constraints)


@pytest.mark.unit
async def test_retrieve_evidence_returns_dict(retriever: EvidenceRetriever) -> None:
    """Test that retrieve_evidence returns a dictionary."""
    now = datetime.now(UTC)
    evidence = await retriever.retrieve_evidence(
        incident_id="inc-001",
        service="demo-api",
        detected_at=now,
    )

    assert isinstance(evidence, dict)


@pytest.mark.unit
async def test_retrieve_evidence_respects_constraints(custom_retriever: EvidenceRetriever) -> None:
    """Test that custom constraints are applied."""
    assert custom_retriever.constraints.time_window_minutes == 15
    assert custom_retriever.constraints.max_log_entries == 50
    assert custom_retriever.constraints.max_metric_points == 25
    assert custom_retriever.constraints.max_trace_samples == 10


@pytest.mark.unit
async def test_retrieve_incident_evidence_convenience_function() -> None:
    """Test the convenience function works correctly."""
    now = datetime.now(UTC)
    evidence = await retrieve_incident_evidence(
        incident_id="inc-002",
        service="demo-api",
        detected_at=now,
    )

    assert isinstance(evidence, dict)


@pytest.mark.unit
async def test_retrieve_evidence_with_custom_constraints_function() -> None:
    """Test convenience function with custom constraints."""
    now = datetime.now(UTC)
    constraints = EvidenceConstraints(time_window_minutes=10)

    evidence = await retrieve_incident_evidence(
        incident_id="inc-003",
        service="demo-api",
        detected_at=now,
        constraints=constraints,
    )

    assert isinstance(evidence, dict)


@pytest.mark.unit
def test_evidence_dataclass_creation() -> None:
    """Test Evidence dataclass can be created."""
    now = datetime.now(UTC)
    evidence = Evidence(
        evidence_id="ev-001",
        source_type="log",
        timestamp=now,
        data={"message": "Error occurred", "level": "ERROR"},
        description="Error log entry",
    )

    assert evidence.evidence_id == "ev-001"
    assert evidence.source_type == "log"
    assert evidence.timestamp == now
    assert evidence.data["message"] == "Error occurred"
    assert evidence.description == "Error log entry"


@pytest.mark.unit
def test_evidence_constraints_defaults() -> None:
    """Test EvidenceConstraints has sensible defaults."""
    constraints = EvidenceConstraints()

    assert constraints.time_window_minutes == 30
    assert constraints.max_log_entries == 100
    assert constraints.max_metric_points == 50
    assert constraints.max_trace_samples == 20
