"""Approval workflow API implementing ADR-0007 governance model."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from packages.contracts.common import ActorType, Digest, Identifier, PrincipalId
from packages.contracts.remediation import Approval, ApprovalDecision, Approver

logger = logging.getLogger(__name__)


class ApprovalRequest(BaseModel):
    """Request to create approval."""

    proposal_id: Identifier
    decision: ApprovalDecision
    approver_identity: PrincipalId
    comment: str | None = Field(None, max_length=4000)
    ttl_minutes: int = Field(60, ge=5, le=240)


def verify_identity(x_user_id: str = Header(...)) -> PrincipalId:
    """Verify user identity."""
    if not x_user_id or len(x_user_id) < 3:
        raise HTTPException(401, "Invalid user")
    return x_user_id


def create_app() -> FastAPI:
    """Create API."""
    app = FastAPI(title="Approval API", version="1.0.0")

    @app.post("/api/v1/approvals", status_code=201)
    async def create_approval(
        req: ApprovalRequest, user: PrincipalId = Depends(verify_identity)
    ) -> dict:
        """Create approval/rejection."""
        if user != req.approver_identity:
            raise HTTPException(403, "Identity mismatch")

        # Stub: would fetch proposal from remediation service
        now = datetime.now(tz=UTC)
        expires = now + timedelta(minutes=req.ttl_minutes)

        approval = Approval(
            approval_id=f"APPR-{req.proposal_id}-{now.strftime('%Y%m%d%H%M%S')}",
            incident_id="INC-STUB",  # Would be fetched from proposal
            proposal_id=req.proposal_id,
            action_hash="sha256:stub",  # Would be computed from proposal
            approver=Approver(actor_type=ActorType.HUMAN, identity=req.approver_identity),
            decision=req.decision,
            comment=req.comment,
            decided_at=now,
            expires_at=expires,
        )

        # Stub: would persist to approval repository
        logger.info(
            "Approval %s created: %s by %s",
            approval.approval_id,
            req.decision.value,
            req.approver_identity,
        )

        return {"approval": approval.model_dump(mode="json")}

    @app.get("/api/v1/approvals/{approval_id}")
    async def get_approval(approval_id: Identifier) -> dict:
        """Get approval details."""
        # Stub: would fetch from repository
        return {"approval_id": approval_id, "status": "pending"}

    @app.get("/api/v1/approvals/pending")
    async def list_pending(limit: int = 50) -> dict:
        """List pending approvals for current user."""
        # Stub: would fetch pending approvals
        return {"approvals": [], "total": 0}

    @app.post("/api/v1/approvals/{approval_id}/validate")
    async def validate(approval_id: Identifier, action_hash: Digest) -> dict:
        """Validate approval."""
        # Stub: would check approval
        return {"valid": True}

    @app.get("/health")
    async def health() -> dict:
        """Health."""
        return {"status": "healthy"}

    return app
