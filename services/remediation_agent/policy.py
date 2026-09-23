"""Risk and policy engine for remediation actions.

Implements explicit policy checks ensuring no direct production mutation,
requiring approval for high-risk actions, and enforcing deny-by-default.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import logging

from services.remediation_agent.proposal import BlastRadius, ProposalCategory, RemediationProposal

logger = logging.getLogger(__name__)


class RiskLevel(StrEnum):
    """Risk levels for remediation actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyDecision(StrEnum):
    """Policy enforcement decisions."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass
class PolicyResult:
    """Result of policy evaluation."""

    decision: PolicyDecision
    risk_level: RiskLevel
    required_approvals: int
    blocked_reason: str | None
    policy_violations: list[str]


class RemediationPolicy:
    """Policy engine enforcing remediation governance rules."""

    def __init__(
        self,
        environment: str = "production",
        blocked_namespaces: set[str] | None = None,
        blocked_resources: set[str] | None = None,
        max_automated_scope: BlastRadius = BlastRadius.SINGLE_POD,
    ) -> None:
        """Initialize policy engine.

        Parameters
        ----------
        environment
            Current environment (production, staging, development)
        blocked_namespaces
            Namespaces where automated actions are forbidden
        blocked_resources
            Resource names that cannot be modified automatically
        max_automated_scope
            Maximum blast radius for any automated action
        """
        self.environment = environment
        self.blocked_namespaces = blocked_namespaces or {
            "kube-system",
            "kube-public",
            "kube-node-lease",
        }
        self.blocked_resources = blocked_resources or {
            "coredns",
            "kube-apiserver",
            "etcd",
        }
        self.max_automated_scope = max_automated_scope

    def evaluate(self, proposal: RemediationProposal, namespace: str = "demo") -> PolicyResult:
        """Evaluate a remediation proposal against policy.

        Parameters
        ----------
        proposal
            Remediation proposal to evaluate
        namespace
            Target Kubernetes namespace

        Returns
        -------
        PolicyResult
            Policy decision with risk assessment
        """
        violations: list[str] = []
        risk_level = self._assess_risk(proposal)

        # Rule 1: No direct production mutation (everything requires approval in production)
        if self.environment == "production" and proposal.category != ProposalCategory.NO_ACTION:
            violations.append("Production actions require explicit human approval")

        # Rule 2: Blocked namespaces
        if namespace in self.blocked_namespaces:
            violations.append(f"Namespace {namespace} is protected from automated changes")
            return PolicyResult(
                decision=PolicyDecision.DENY,
                risk_level=RiskLevel.CRITICAL,
                required_approvals=0,
                blocked_reason=f"Blocked namespace: {namespace}",
                policy_violations=violations,
            )

        # Rule 3: Check if resource is in blocked list
        for resource in self.blocked_resources:
            if any(resource in cmd for cmd in proposal.commands):
                violations.append(f"Resource {resource} is protected from automated changes")
                return PolicyResult(
                    decision=PolicyDecision.DENY,
                    risk_level=RiskLevel.CRITICAL,
                    required_approvals=0,
                    blocked_reason=f"Blocked resource: {resource}",
                    policy_violations=violations,
                )

        # Rule 4: Maximum automated scope
        if self._compare_blast_radius(proposal.blast_radius, self.max_automated_scope) > 0:
            violations.append(
                f"Blast radius {proposal.blast_radius} exceeds maximum {self.max_automated_scope}"
            )

        # Rule 5: High-risk actions require additional approval
        if risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            violations.append("High-risk actions require additional human approval")

        # Rule 6: Production rollbacks always require approval
        if self.environment == "production" and proposal.category == ProposalCategory.ROLLBACK:
            violations.append("Production rollbacks require explicit approval")

        # Determine decision based on violations and risk
        decision = self._make_decision(proposal, risk_level, violations)

        # Calculate required approvals
        required_approvals = self._calculate_required_approvals(proposal, risk_level, decision)

        logger.info(
            "Policy evaluation for proposal %s: %s (risk: %s, approvals: %d, violations: %d)",
            proposal.proposal_id,
            decision,
            risk_level,
            required_approvals,
            len(violations),
        )

        return PolicyResult(
            decision=decision,
            risk_level=risk_level,
            required_approvals=required_approvals,
            blocked_reason=None if decision != PolicyDecision.DENY else violations[0],
            policy_violations=violations,
        )

    def _assess_risk(self, proposal: RemediationProposal) -> RiskLevel:
        """Assess risk level of a proposal."""
        # Rollbacks are always high risk
        if proposal.category == ProposalCategory.ROLLBACK:
            return RiskLevel.HIGH

        # Configuration changes are high risk
        if proposal.category == ProposalCategory.CONFIGURATION_CHANGE:
            return RiskLevel.HIGH

        # Assess by blast radius
        if proposal.blast_radius in {BlastRadius.CLUSTER, BlastRadius.MULTI_CLUSTER}:
            return RiskLevel.CRITICAL
        if proposal.blast_radius == BlastRadius.NAMESPACE:
            return RiskLevel.HIGH
        if proposal.blast_radius == BlastRadius.SERVICE:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _compare_blast_radius(self, actual: BlastRadius, limit: BlastRadius) -> int:
        """Compare blast radius levels. Returns: -1 (less), 0 (equal), 1 (greater)."""
        order = [
            BlastRadius.SINGLE_POD,
            BlastRadius.SERVICE,
            BlastRadius.NAMESPACE,
            BlastRadius.CLUSTER,
            BlastRadius.MULTI_CLUSTER,
        ]
        actual_idx = order.index(actual)
        limit_idx = order.index(limit)

        if actual_idx < limit_idx:
            return -1
        if actual_idx == limit_idx:
            return 0
        return 1

    def _make_decision(
        self, proposal: RemediationProposal, risk_level: RiskLevel, violations: list[str]
    ) -> PolicyDecision:
        """Make policy decision based on risk and violations."""
        # NO_ACTION is always allowed
        if proposal.category == ProposalCategory.NO_ACTION:
            return PolicyDecision.ALLOW

        # Critical risk or blocked resources = deny
        if risk_level == RiskLevel.CRITICAL:
            return PolicyDecision.DENY

        # Any violations in production = require approval
        if violations and self.environment == "production":
            return PolicyDecision.REQUIRE_APPROVAL

        # Deny by default - all production actions require approval
        return PolicyDecision.REQUIRE_APPROVAL

    def _calculate_required_approvals(
        self, proposal: RemediationProposal, risk_level: RiskLevel, decision: PolicyDecision
    ) -> int:
        """Calculate number of required approvals."""
        if decision == PolicyDecision.DENY:
            return 0  # Cannot be approved

        if decision == PolicyDecision.ALLOW:
            return 0  # No approval needed

        # Base approval count
        base = proposal.required_approvals

        # Add approvals based on risk
        if risk_level == RiskLevel.HIGH:
            base += 1
        elif risk_level == RiskLevel.CRITICAL:
            base += 2

        # Production always needs at least one approval
        if self.environment == "production":
            base = max(base, 1)

        return base
