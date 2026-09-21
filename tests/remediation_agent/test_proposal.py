"""Tests for remediation proposal engine."""

from __future__ import annotations

import pytest

from packages.contracts.common import Confidence
from packages.contracts.incidents import CauseCategory
from services.remediation_agent.proposal import (
    BlastRadius,
    ProposalCategory,
    ProposalEngine,
    RemediationProposal,
)


@pytest.fixture
def engine() -> ProposalEngine:
    """Return a proposal engine instance."""
    return ProposalEngine()


@pytest.mark.unit
def test_generate_rollback_proposal_for_deployment_regression(engine: ProposalEngine) -> None:
    """Test that deployment regression generates rollback proposal."""
    proposal = engine.generate_proposal(
        incident_id="inc-001",
        cause_category=CauseCategory.DEPLOYMENT_REGRESSION,
        evidence_ids=["ev-001", "ev-002"],
        confidence=0.85,
        service="demo-api",
    )

    assert proposal.incident_id == "inc-001"
    assert proposal.category == ProposalCategory.ROLLBACK
    assert "roll back" in proposal.title.lower()
    assert proposal.blast_radius == BlastRadius.SERVICE
    assert proposal.required_approvals == 1
    assert not proposal.safe_to_automate
    assert len(proposal.commands) > 0
    assert "kubectl rollout undo" in proposal.commands[0]


@pytest.mark.unit
def test_generate_scale_proposal_for_resource_exhaustion(engine: ProposalEngine) -> None:
    """Test that resource exhaustion generates scale-up proposal."""
    proposal = engine.generate_proposal(
        incident_id="inc-002",
        cause_category=CauseCategory.RESOURCE_EXHAUSTION,
        evidence_ids=["ev-003"],
        confidence=0.90,
        service="demo-api",
    )

    assert proposal.category == ProposalCategory.RESOURCE_ADJUSTMENT
    assert "resource" in proposal.title.lower()
    assert proposal.blast_radius == BlastRadius.SERVICE
    assert len(proposal.commands) > 0
    assert "kubectl scale" in proposal.commands[0]


@pytest.mark.unit
def test_generate_restart_proposal_for_dependency_failure(engine: ProposalEngine) -> None:
    """Test that dependency failure generates restart proposal."""
    proposal = engine.generate_proposal(
        incident_id="inc-003",
        cause_category=CauseCategory.DEPENDENCY_FAILURE,
        evidence_ids=["ev-004", "ev-005"],
        confidence=0.75,
        service="demo-api",
    )

    assert proposal.category == ProposalCategory.RESTART_ROLLOUT
    assert "restart" in proposal.title.lower()
    assert proposal.blast_radius == BlastRadius.SERVICE
    assert "kubectl rollout restart" in proposal.commands[0]


@pytest.mark.unit
def test_generate_config_proposal_for_configuration_error(engine: ProposalEngine) -> None:
    """Test that configuration error generates config fix proposal."""
    proposal = engine.generate_proposal(
        incident_id="inc-004",
        cause_category=CauseCategory.CONFIGURATION_ERROR,
        evidence_ids=["ev-006"],
        confidence=0.70,
        service="demo-api",
    )

    assert proposal.category == ProposalCategory.CONFIGURATION_CHANGE
    assert "configuration" in proposal.title.lower()
    assert proposal.required_approvals >= 2  # Config changes need more approval
    assert not proposal.safe_to_automate


@pytest.mark.unit
def test_generate_no_action_proposal_for_unknown_cause(engine: ProposalEngine) -> None:
    """Test that unknown causes generate manual investigation proposal."""
    proposal = engine.generate_proposal(
        incident_id="inc-005",
        cause_category=CauseCategory.UNKNOWN,
        evidence_ids=["ev-007"],
        confidence=0.30,
        service="demo-api",
    )

    assert proposal.category == ProposalCategory.NO_ACTION
    assert "manual" in proposal.title.lower() or "investigation" in proposal.title.lower()
    assert proposal.required_approvals == 0
    assert not proposal.safe_to_automate


@pytest.mark.unit
def test_proposal_includes_governance_fields(engine: ProposalEngine) -> None:
    """Test that all proposals include required governance fields."""
    proposal = engine.generate_proposal(
        incident_id="inc-006",
        cause_category=CauseCategory.DEPLOYMENT_REGRESSION,
        evidence_ids=["ev-008"],
        confidence=0.85,
        service="demo-api",
    )

    # Check all required governance fields are present
    assert proposal.proposal_id
    assert proposal.incident_id
    assert proposal.category
    assert proposal.title
    assert proposal.rationale
    assert proposal.evidence_ids
    assert proposal.expected_impact
    assert proposal.blast_radius
    assert proposal.rollback_plan
    assert isinstance(proposal.confidence, Confidence)
    assert isinstance(proposal.required_approvals, int)
    assert isinstance(proposal.safe_to_automate, bool)
    assert isinstance(proposal.commands, list)


@pytest.mark.unit
def test_proposal_ids_are_unique(engine: ProposalEngine) -> None:
    """Test that proposal IDs increment correctly."""
    proposal1 = engine.generate_proposal(
        incident_id="inc-007",
        cause_category=CauseCategory.DEPLOYMENT_REGRESSION,
        evidence_ids=["ev-009"],
        confidence=0.85,
        service="demo-api",
    )

    proposal2 = engine.generate_proposal(
        incident_id="inc-008",
        cause_category=CauseCategory.RESOURCE_EXHAUSTION,
        evidence_ids=["ev-010"],
        confidence=0.90,
        service="demo-api",
    )

    assert proposal1.proposal_id != proposal2.proposal_id


@pytest.mark.unit
def test_evidence_ids_are_preserved(engine: ProposalEngine) -> None:
    """Test that evidence IDs are correctly attached to proposals."""
    evidence_ids = ["ev-011", "ev-012", "ev-013"]

    proposal = engine.generate_proposal(
        incident_id="inc-009",
        cause_category=CauseCategory.DEPLOYMENT_REGRESSION,
        evidence_ids=evidence_ids,
        confidence=0.85,
        service="demo-api",
    )

    assert proposal.evidence_ids == evidence_ids


@pytest.mark.unit
def test_confidence_is_preserved(engine: ProposalEngine) -> None:
    """Test that confidence value is correctly preserved."""
    confidence_value = 0.88

    proposal = engine.generate_proposal(
        incident_id="inc-010",
        cause_category=CauseCategory.DEPLOYMENT_REGRESSION,
        evidence_ids=["ev-014"],
        confidence=confidence_value,
        service="demo-api",
    )

    assert float(proposal.confidence) == confidence_value
