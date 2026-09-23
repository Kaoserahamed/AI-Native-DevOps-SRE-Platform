"""Tests for remediation policy engine."""

from __future__ import annotations

import pytest

from packages.contracts.common import Confidence
from services.remediation_agent.policy import (
    PolicyDecision,
    RemediationPolicy,
    RiskLevel,
)
from services.remediation_agent.proposal import (
    BlastRadius,
    ProposalCategory,
    RemediationProposal,
)


@pytest.fixture
def production_policy() -> RemediationPolicy:
    """Return a policy engine for production environment."""
    return RemediationPolicy(environment="production")


@pytest.fixture
def staging_policy() -> RemediationPolicy:
    """Return a policy engine for staging environment."""
    return RemediationPolicy(environment="staging")


@pytest.fixture
def sample_rollback_proposal() -> RemediationProposal:
    """Return a sample rollback proposal."""
    return RemediationProposal(
        proposal_id="prop-001",
        incident_id="inc-001",
        category=ProposalCategory.ROLLBACK,
        title="Roll back demo-api",
        rationale="Deployment regression",
        evidence_ids=["ev-001"],
        expected_impact="Error rate returns to baseline",
        blast_radius=BlastRadius.SERVICE,
        rollback_plan="Scale down new pods",
        confidence=Confidence(0.85),
        required_approvals=1,
        safe_to_automate=False,
        commands=["kubectl rollout undo deployment/demo-api -n demo"],
    )


@pytest.mark.unit
def test_production_actions_require_approval(
    production_policy: RemediationPolicy, sample_rollback_proposal: RemediationProposal
) -> None:
    """Test that all production actions require approval."""
    result = production_policy.evaluate(sample_rollback_proposal, namespace="demo")

    assert result.decision == PolicyDecision.REQUIRE_APPROVAL
    assert result.required_approvals >= 1
    assert "Production" in " ".join(result.policy_violations)


@pytest.mark.unit
def test_blocked_namespace_denied(
    production_policy: RemediationPolicy, sample_rollback_proposal: RemediationProposal
) -> None:
    """Test that actions in blocked namespaces are denied."""
    result = production_policy.evaluate(sample_rollback_proposal, namespace="kube-system")

    assert result.decision == PolicyDecision.DENY
    assert result.risk_level == RiskLevel.CRITICAL
    assert result.blocked_reason is not None
    assert "kube-system" in result.blocked_reason


@pytest.mark.unit
def test_blocked_resource_denied(production_policy: RemediationPolicy) -> None:
    """Test that actions on blocked resources are denied."""
    proposal = RemediationProposal(
        proposal_id="prop-002",
        incident_id="inc-002",
        category=ProposalCategory.RESTART_ROLLOUT,
        title="Restart coredns",
        rationale="DNS issues",
        evidence_ids=["ev-002"],
        expected_impact="DNS recovers",
        blast_radius=BlastRadius.CLUSTER,
        rollback_plan="N/A",
        confidence=Confidence(0.90),
        required_approvals=1,
        safe_to_automate=False,
        commands=["kubectl rollout restart deployment/coredns -n kube-system"],
    )

    result = production_policy.evaluate(proposal, namespace="demo")

    assert result.decision == PolicyDecision.DENY
    assert result.blocked_reason is not None
    assert "coredns" in result.blocked_reason


@pytest.mark.unit
def test_rollback_is_high_risk(
    production_policy: RemediationPolicy, sample_rollback_proposal: RemediationProposal
) -> None:
    """Test that rollbacks are assessed as high risk."""
    result = production_policy.evaluate(sample_rollback_proposal, namespace="demo")

    assert result.risk_level == RiskLevel.HIGH


@pytest.mark.unit
def test_config_change_is_high_risk(production_policy: RemediationPolicy) -> None:
    """Test that configuration changes are high risk."""
    proposal = RemediationProposal(
        proposal_id="prop-003",
        incident_id="inc-003",
        category=ProposalCategory.CONFIGURATION_CHANGE,
        title="Fix config",
        rationale="Config error",
        evidence_ids=["ev-003"],
        expected_impact="Errors stop",
        blast_radius=BlastRadius.SERVICE,
        rollback_plan="Revert ConfigMap",
        confidence=Confidence(0.75),
        required_approvals=2,
        safe_to_automate=False,
        commands=["kubectl apply -f config.yaml"],
    )

    result = production_policy.evaluate(proposal, namespace="demo")

    assert result.risk_level == RiskLevel.HIGH


@pytest.mark.unit
def test_cluster_blast_radius_is_critical_risk(production_policy: RemediationPolicy) -> None:
    """Test that cluster-wide actions are critical risk."""
    proposal = RemediationProposal(
        proposal_id="prop-004",
        incident_id="inc-004",
        category=ProposalCategory.RESOURCE_ADJUSTMENT,
        title="Scale cluster",
        rationale="Load spike",
        evidence_ids=["ev-004"],
        expected_impact="Capacity increases",
        blast_radius=BlastRadius.CLUSTER,
        rollback_plan="Scale down",
        confidence=Confidence(0.80),
        required_approvals=1,
        safe_to_automate=False,
        commands=["kubectl scale --all"],
    )

    result = production_policy.evaluate(proposal, namespace="demo")

    assert result.risk_level == RiskLevel.CRITICAL
    assert result.decision == PolicyDecision.DENY


@pytest.mark.unit
def test_no_action_proposal_allowed(production_policy: RemediationPolicy) -> None:
    """Test that NO_ACTION proposals are always allowed."""
    proposal = RemediationProposal(
        proposal_id="prop-005",
        incident_id="inc-005",
        category=ProposalCategory.NO_ACTION,
        title="Manual investigation",
        rationale="Unknown cause",
        evidence_ids=["ev-005"],
        expected_impact="No action",
        blast_radius=BlastRadius.SINGLE_POD,
        rollback_plan="N/A",
        confidence=Confidence(0.40),
        required_approvals=0,
        safe_to_automate=False,
        commands=["# Manual review"],
    )

    result = production_policy.evaluate(proposal, namespace="demo")

    assert result.decision == PolicyDecision.ALLOW
    assert result.required_approvals == 0


@pytest.mark.unit
def test_high_risk_requires_additional_approval(
    production_policy: RemediationPolicy, sample_rollback_proposal: RemediationProposal
) -> None:
    """Test that high-risk actions require additional approvals."""
    result = production_policy.evaluate(sample_rollback_proposal, namespace="demo")

    # Rollback has required_approvals=1, high risk adds +1, production ensures at least 1
    assert result.required_approvals >= 2


@pytest.mark.unit
def test_staging_policy_never_stricter_than_production(
    staging_policy: RemediationPolicy, sample_rollback_proposal: RemediationProposal
) -> None:
    """Test that a staging policy never demands more approvals than production.

    Both engines require the same base approval count for this proposal, so the invariant under test
    is the ordering between environments rather than a hard-coded number: relaxing the environment
    must never tighten the gate.
    """
    prod_result = RemediationPolicy(environment="production").evaluate(
        sample_rollback_proposal, namespace="demo"
    )
    staging_result = staging_policy.evaluate(sample_rollback_proposal, namespace="demo")

    assert prod_result.decision == PolicyDecision.REQUIRE_APPROVAL
    assert staging_result.decision in {PolicyDecision.REQUIRE_APPROVAL, PolicyDecision.ALLOW}
    assert staging_result.required_approvals <= prod_result.required_approvals


@pytest.mark.unit
def test_policy_violations_are_recorded(
    production_policy: RemediationPolicy, sample_rollback_proposal: RemediationProposal
) -> None:
    """Test that policy violations are properly recorded."""
    result = production_policy.evaluate(sample_rollback_proposal, namespace="demo")

    assert len(result.policy_violations) > 0
    assert all(isinstance(v, str) for v in result.policy_violations)


@pytest.mark.unit
def test_custom_blocked_resources(sample_rollback_proposal: RemediationProposal) -> None:
    """Test policy with custom blocked resources."""
    policy = RemediationPolicy(
        environment="production",
        blocked_resources={"demo-api", "critical-service"},
    )

    result = policy.evaluate(sample_rollback_proposal, namespace="demo")

    # demo-api is in the command, should be denied
    assert result.decision == PolicyDecision.DENY
    assert result.blocked_reason is not None
    assert "demo-api" in result.blocked_reason


@pytest.mark.unit
def test_service_blast_radius_is_medium_risk(production_policy: RemediationPolicy) -> None:
    """Test that service-level actions are medium risk."""
    proposal = RemediationProposal(
        proposal_id="prop-006",
        incident_id="inc-006",
        category=ProposalCategory.RESTART_ROLLOUT,
        title="Restart service",
        rationale="Connection issues",
        evidence_ids=["ev-006"],
        expected_impact="Connections recover",
        blast_radius=BlastRadius.SERVICE,
        rollback_plan="N/A",
        confidence=Confidence(0.80),
        required_approvals=1,
        safe_to_automate=False,
        commands=["kubectl rollout restart deployment/app -n demo"],
    )

    result = production_policy.evaluate(proposal, namespace="demo")

    assert result.risk_level == RiskLevel.MEDIUM
