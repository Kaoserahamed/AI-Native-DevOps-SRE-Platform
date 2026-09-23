"""Tests for the typed remediation policy evaluator."""

from datetime import UTC, datetime

import pytest

from packages.contracts.agents import PolicyOutcome
from packages.contracts.common import Environment
from packages.contracts.remediation import (
    ActionTarget,
    BlastRadius,
    RemediationCategory,
    RemediationProposal,
    RiskLevel,
)
from packages.policy import PolicyEngine, PolicyEvaluationRequest


def proposal(
    *,
    environment: Environment = Environment.PRODUCTION,
    blast_radius: BlastRadius = BlastRadius.WORKLOAD,
    risk: RiskLevel = RiskLevel.MEDIUM,
) -> RemediationProposal:
    return RemediationProposal(
        proposal_id="PROP-001",
        incident_id="INC-001",
        category=RemediationCategory.RESTART_OR_ROLLOUT,
        target=ActionTarget(
            environment=environment,
            namespace="platform",
            workload="demo-api",
        ),
        rationale="Restore the unhealthy workload.",
        evidence_ids=["EVID-001"],
        expected_impact="Return the workload to its healthy state.",
        blast_radius=blast_radius,
        rollback_plan="Restore the previous deployment revision.",
        confidence=0.9,
        required_permissions=["workload.restart"],
        risk=risk,
        created_at=datetime(2026, 9, 23, tzinfo=UTC),
    )


def test_production_workload_requires_one_human_approval() -> None:
    result = PolicyEngine().evaluate(PolicyEvaluationRequest(proposal=proposal()))

    assert result.allowed is False
    assert result.verdict.outcome is PolicyOutcome.REQUIRE_APPROVAL
    assert result.verdict.required_approvals == 1


def test_production_workload_is_allowed_after_approval() -> None:
    result = PolicyEngine().evaluate(
        PolicyEvaluationRequest(proposal=proposal(), approval_count=1, human_approved=True)
    )

    assert result.allowed is True
    assert result.verdict.outcome is PolicyOutcome.ALLOW
    assert result.verdict.violations == []


def test_high_risk_cluster_requires_two_approvals() -> None:
    result = PolicyEngine().evaluate(
        PolicyEvaluationRequest(
            proposal=proposal(blast_radius=BlastRadius.CLUSTER, risk=RiskLevel.HIGH),
            approval_count=1,
            human_approved=True,
        )
    )

    assert result.verdict.outcome is PolicyOutcome.REQUIRE_APPROVAL
    assert result.verdict.required_approvals == 2


def test_non_production_proposal_does_not_need_approval() -> None:
    result = PolicyEngine().evaluate(
        PolicyEvaluationRequest(
            proposal=proposal(environment=Environment.DEVELOPMENT),
        )
    )

    assert result.allowed is True
    assert result.verdict.required_approvals == 0


def test_approval_flag_without_record_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one approval"):
        PolicyEvaluationRequest(proposal=proposal(), human_approved=True)
