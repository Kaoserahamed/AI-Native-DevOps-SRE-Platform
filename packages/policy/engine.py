"""Deny-by-default remediation policy evaluation."""

from __future__ import annotations

from datetime import UTC, datetime

from packages.contracts.agents import PolicyOutcome, PolicyVerdict
from packages.contracts.remediation import BlastRadius, RemediationProposal, RiskLevel
from packages.policy.models import PolicyEvaluationRequest, PolicyEvaluationResponse


class PolicyEngine:
    """Evaluate the approval requirements for a remediation proposal."""

    def evaluate(self, request: PolicyEvaluationRequest) -> PolicyEvaluationResponse:
        """Return an auditable verdict without executing the proposed action."""
        proposal = request.proposal
        required_approvals = self._required_approvals(proposal)
        reasons: list[str] = []

        if required_approvals == 0:
            outcome = PolicyOutcome.ALLOW
            reasons.append("proposal is limited to a non-production or repository-only target")
        elif not request.human_approved or request.approval_count < required_approvals:
            outcome = PolicyOutcome.REQUIRE_APPROVAL
            reasons.append(f"at least {required_approvals} human approval(s) are required")
        else:
            outcome = PolicyOutcome.ALLOW
            reasons.append("required human approval threshold was met")

        verdict = PolicyVerdict(
            outcome=outcome,
            evaluated_at=datetime.now(tz=UTC),
            required_approvals=required_approvals,
            violations=reasons if outcome is not PolicyOutcome.ALLOW else [],
        )
        return PolicyEvaluationResponse(proposal_id=proposal.proposal_id, verdict=verdict)

    @staticmethod
    def _required_approvals(proposal: RemediationProposal) -> int:
        """Calculate the minimum human approvals for a proposal's blast radius and risk."""
        if proposal.target.environment.value != "production":
            return 0
        if proposal.blast_radius is BlastRadius.REPOSITORY_ONLY:
            return 0
        if proposal.risk is RiskLevel.HIGH or proposal.blast_radius is BlastRadius.CLUSTER:
            return 2
        return 1
