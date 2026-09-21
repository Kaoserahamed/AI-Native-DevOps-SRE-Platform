"""Remediation proposal generation engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from packages.contracts.common import Confidence, Identifier
from packages.contracts.incidents import CauseCategory

logger = logging.getLogger(__name__)


class ProposalCategory(StrEnum):
    """Allowed remediation proposal categories."""

    RESTART_ROLLOUT = "restart_rollout"
    ROLLBACK = "rollback"
    CONFIGURATION_CHANGE = "configuration_change"
    RESOURCE_ADJUSTMENT = "resource_adjustment"
    CODE_FIX = "code_fix"
    ALERT_TUNING = "alert_tuning"
    COST_OPTIMIZATION = "cost_optimization"
    NO_ACTION = "no_action"


class BlastRadius(StrEnum):
    """Impact scope of a remediation action."""

    SINGLE_POD = "single_pod"
    SERVICE = "service"
    NAMESPACE = "namespace"
    CLUSTER = "cluster"
    MULTI_CLUSTER = "multi_cluster"


@dataclass
class RemediationProposal:
    """A remediation proposal with all required governance fields."""

    proposal_id: Identifier
    incident_id: Identifier
    category: ProposalCategory
    title: str
    rationale: str
    evidence_ids: list[Identifier]
    expected_impact: str
    blast_radius: BlastRadius
    rollback_plan: str
    confidence: Confidence
    required_approvals: int
    safe_to_automate: bool
    commands: list[str]  # Actual commands to execute


class ProposalEngine:
    """Generates remediation proposals from incident analysis."""

    def __init__(self) -> None:
        """Initialize proposal engine."""
        self._proposal_counter = 0

    def generate_proposal(
        self,
        incident_id: Identifier,
        cause_category: CauseCategory,
        evidence_ids: list[Identifier],
        confidence: float,
        service: str,
    ) -> RemediationProposal:
        """Generate a remediation proposal based on incident analysis.

        Parameters
        ----------
        incident_id
            The incident being addressed
        cause_category
            Diagnosed root cause category
        evidence_ids
            Evidence supporting the diagnosis
        confidence
            Diagnosis confidence level
        service
            Affected service name

        Returns
        -------
        RemediationProposal
            Generated proposal with governance fields
        """
        self._proposal_counter += 1
        proposal_id = f"prop-{self._proposal_counter:04d}"

        # Map cause categories to remediation strategies
        proposal = self._create_proposal_for_cause(
            proposal_id=proposal_id,
            incident_id=incident_id,
            cause_category=cause_category,
            evidence_ids=evidence_ids,
            confidence=Confidence(confidence),
            service=service,
        )

        logger.info(
            "Generated proposal %s for incident %s: %s (confidence: %.2f)",
            proposal_id,
            incident_id,
            proposal.category,
            confidence,
        )

        return proposal

    def _create_proposal_for_cause(
        self,
        proposal_id: Identifier,
        incident_id: Identifier,
        cause_category: CauseCategory,
        evidence_ids: list[Identifier],
        confidence: Confidence,
        service: str,
    ) -> RemediationProposal:
        """Create a specific proposal based on cause category."""
        if cause_category == CauseCategory.DEPLOYMENT_REGRESSION:
            return self._rollback_proposal(
                proposal_id, incident_id, evidence_ids, confidence, service
            )
        elif cause_category == CauseCategory.RESOURCE_EXHAUSTION:
            return self._scale_up_proposal(
                proposal_id, incident_id, evidence_ids, confidence, service
            )
        elif cause_category == CauseCategory.DEPENDENCY_FAILURE:
            return self._restart_proposal(
                proposal_id, incident_id, evidence_ids, confidence, service
            )
        elif cause_category == CauseCategory.CONFIGURATION_ERROR:
            return self._config_fix_proposal(
                proposal_id, incident_id, evidence_ids, confidence, service
            )
        else:
            return self._manual_investigation_proposal(
                proposal_id, incident_id, evidence_ids, confidence, service
            )

    def _rollback_proposal(
        self,
        proposal_id: Identifier,
        incident_id: Identifier,
        evidence_ids: list[Identifier],
        confidence: Confidence,
        service: str,
    ) -> RemediationProposal:
        """Create a rollback proposal for deployment regressions."""
        return RemediationProposal(
            proposal_id=proposal_id,
            incident_id=incident_id,
            category=ProposalCategory.ROLLBACK,
            title=f"Roll back {service} to previous stable version",
            rationale="Error rate spiked after recent deployment. Rolling back to last known good version.",
            evidence_ids=evidence_ids,
            expected_impact="Error rate should return to baseline within 5 minutes",
            blast_radius=BlastRadius.SERVICE,
            rollback_plan="If rollback fails, manually scale down new pods and scale up old ReplicaSet",
            confidence=confidence,
            required_approvals=1,
            safe_to_automate=False,  # Requires human approval
            commands=[
                f"kubectl rollout undo deployment/{service} -n demo",
                f"kubectl rollout status deployment/{service} -n demo --timeout=5m",
            ],
        )

    def _scale_up_proposal(
        self,
        proposal_id: Identifier,
        incident_id: Identifier,
        evidence_ids: list[Identifier],
        confidence: Confidence,
        service: str,
    ) -> RemediationProposal:
        """Create a scale-up proposal for resource exhaustion."""
        return RemediationProposal(
            proposal_id=proposal_id,
            incident_id=incident_id,
            category=ProposalCategory.RESOURCE_ADJUSTMENT,
            title=f"Increase resource limits for {service}",
            rationale="Memory/CPU usage at or near limits. Scaling up to handle load.",
            evidence_ids=evidence_ids,
            expected_impact="OOM kills should stop, latency should decrease",
            blast_radius=BlastRadius.SERVICE,
            rollback_plan="Reduce resource limits back to original values if no improvement",
            confidence=confidence,
            required_approvals=1,
            safe_to_automate=False,
            commands=[
                f"kubectl scale deployment/{service} -n demo --replicas=4",
                f"kubectl rollout status deployment/{service} -n demo --timeout=5m",
            ],
        )

    def _restart_proposal(
        self,
        proposal_id: Identifier,
        incident_id: Identifier,
        evidence_ids: list[Identifier],
        confidence: Confidence,
        service: str,
    ) -> RemediationProposal:
        """Create a restart proposal for dependency failures."""
        return RemediationProposal(
            proposal_id=proposal_id,
            incident_id=incident_id,
            category=ProposalCategory.RESTART_ROLLOUT,
            title=f"Restart {service} pods to recover connections",
            rationale="Service unable to connect to dependencies. Restart may re-establish connections.",
            evidence_ids=evidence_ids,
            expected_impact="Connection errors should decrease within 2 minutes",
            blast_radius=BlastRadius.SERVICE,
            rollback_plan="No rollback needed - restart is non-destructive",
            confidence=confidence,
            required_approvals=1,
            safe_to_automate=False,
            commands=[
                f"kubectl rollout restart deployment/{service} -n demo",
                f"kubectl rollout status deployment/{service} -n demo --timeout=5m",
            ],
        )

    def _config_fix_proposal(
        self,
        proposal_id: Identifier,
        incident_id: Identifier,
        evidence_ids: list[Identifier],
        confidence: Confidence,
        service: str,
    ) -> RemediationProposal:
        """Create a configuration fix proposal."""
        return RemediationProposal(
            proposal_id=proposal_id,
            incident_id=incident_id,
            category=ProposalCategory.CONFIGURATION_CHANGE,
            title=f"Review and correct {service} configuration",
            rationale="Configuration appears incorrect based on error patterns.",
            evidence_ids=evidence_ids,
            expected_impact="Configuration-related errors should stop",
            blast_radius=BlastRadius.SERVICE,
            rollback_plan="Revert ConfigMap to previous version and restart pods",
            confidence=confidence,
            required_approvals=2,  # Higher approval for config changes
            safe_to_automate=False,
            commands=[
                f"# Manual review of ConfigMap required",
                f"kubectl get configmap {service}-config -n demo -o yaml",
            ],
        )

    def _manual_investigation_proposal(
        self,
        proposal_id: Identifier,
        incident_id: Identifier,
        evidence_ids: list[Identifier],
        confidence: Confidence,
        service: str,
    ) -> RemediationProposal:
        """Create a no-action proposal requiring manual investigation."""
        return RemediationProposal(
            proposal_id=proposal_id,
            incident_id=incident_id,
            category=ProposalCategory.NO_ACTION,
            title=f"Manual investigation required for {service}",
            rationale="Root cause unclear or confidence too low for automated remediation.",
            evidence_ids=evidence_ids,
            expected_impact="No automated action - human investigation needed",
            blast_radius=BlastRadius.SINGLE_POD,  # Minimal - observation only
            rollback_plan="N/A - no action taken",
            confidence=confidence,
            required_approvals=0,  # No action to approve
            safe_to_automate=False,
            commands=[
                f"# Review evidence and investigate manually",
                f"kubectl logs -l app.kubernetes.io/name={service} -n demo --tail=100",
            ],
        )
