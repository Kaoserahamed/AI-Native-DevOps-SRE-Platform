"""Wire models for policy evaluation."""

from __future__ import annotations

from pydantic import Field, computed_field, model_validator

from packages.contracts.agents import PolicyOutcome, PolicyVerdict
from packages.contracts.common import PlatformModel
from packages.contracts.remediation import RemediationProposal


class PolicyEvaluationRequest(PlatformModel):
    """Inputs required to evaluate one remediation proposal."""

    proposal: RemediationProposal
    approval_count: int = Field(default=0, ge=0)
    human_approved: bool = False

    @model_validator(mode="after")
    def validate_approval(self) -> PolicyEvaluationRequest:
        """Prevent an approval flag without an actual approval record count."""
        if self.human_approved and self.approval_count < 1:
            raise ValueError("human_approved requires at least one approval")
        return self


class PolicyEvaluationResponse(PlatformModel):
    """The typed, auditable result of evaluating a proposal."""

    proposal_id: str
    verdict: PolicyVerdict

    @computed_field(  # type: ignore[prop-decorator]
        description="Whether the proposal may proceed without further human action."
    )
    @property
    def allowed(self) -> bool:
        """Return whether the proposal may proceed."""
        return self.verdict.outcome is PolicyOutcome.ALLOW
