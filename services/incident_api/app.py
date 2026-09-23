"""Incident Lifecycle API.

Provides RESTful endpoints for incident management, evidence tracking,
and state transitions.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
import os

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel

from packages.contracts.audit import ActorType, AuditEntry
from packages.contracts.common import Identifier
from packages.contracts.evidence import Evidence
from packages.contracts.incidents import Incident, IncidentStatus
from packages.observability.logging_config import (
    configure_logging,
    get_logger,
)
from packages.persistence.repositories import (
    AuditRepository,
    EvidenceRepository,
    IncidentRepository,
)

# Configure structured logging on module import
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    service_name="incident-api",
    environment=os.getenv("ENVIRONMENT", "development"),
    enable_sentry=os.getenv("SENTRY_DSN") is not None,
    sentry_dsn=os.getenv("SENTRY_DSN"),
)

logger = get_logger(__name__)


class IncidentCreateRequest(BaseModel):
    """Request to create a new incident."""

    incident: Incident


class IncidentUpdateRequest(BaseModel):
    """Request to update incident status or details."""

    status: IncidentStatus | None = None
    resolution_summary: str | None = None
    post_incident_notes: str | None = None


class EvidenceAttachRequest(BaseModel):
    """Request to attach evidence to an incident."""

    evidence: Evidence


class IncidentListResponse(BaseModel):
    """Response with list of incidents."""

    incidents: list[Incident]
    total: int


class EvidenceListResponse(BaseModel):
    """Response with list of evidence items."""

    evidence: list[Evidence]
    total: int


# Dependency injection placeholders
_incident_repo: IncidentRepository | None = None
_evidence_repo: EvidenceRepository | None = None
_audit_repo: AuditRepository | None = None


def get_incident_repo() -> IncidentRepository:
    """Get incident repository."""
    if _incident_repo is None:
        raise RuntimeError("Incident repository not initialized")
    return _incident_repo


def get_evidence_repo() -> EvidenceRepository:
    """Get evidence repository."""
    if _evidence_repo is None:
        raise RuntimeError("Evidence repository not initialized")
    return _evidence_repo


def get_audit_repo() -> AuditRepository:
    """Get audit repository."""
    if _audit_repo is None:
        raise RuntimeError("Audit repository not initialized")
    return _audit_repo


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan."""
    logger.info(
        "incident_api_starting",
        version="1.0.0",
        environment=os.getenv("ENVIRONMENT", "development"),
    )
    yield
    logger.info("incident_api_shutting_down")


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="Incident Lifecycle API",
        description="RESTful API for incident management and evidence tracking",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.post("/api/v1/incidents", status_code=status.HTTP_201_CREATED, response_model=Incident)
    async def create_incident(
        request: IncidentCreateRequest,
        incident_repo: IncidentRepository = Depends(get_incident_repo),
        audit_repo: AuditRepository = Depends(get_audit_repo),
    ) -> Incident:
        """Create a new incident."""
        incident = request.incident

        # Check for duplicate
        existing = await incident_repo.find_by_id(incident.incident_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Incident {incident.incident_id} already exists",
            )

        # Save incident
        await incident_repo.save(incident)

        # Audit log
        now = datetime.now(tz=UTC)
        audit_entry = AuditEntry(
            audit_id=f"audit-incident-{incident.incident_id}-{now.strftime('%Y%m%d%H%M%S')}",
            timestamp=now,
            actor_type=ActorType.AGENT,
            actor_id="incident-detector",
            action="incident.create",
            resource_type="incident",
            resource_id=incident.incident_id,
            outcome="success",
            details={
                "severity": incident.severity.value,
                "service": incident.service.name,
                "environment": incident.service.environment.value,
            },
        )
        await audit_repo.append(audit_entry)

        logger.info("Created incident %s (severity: %s)", incident.incident_id, incident.severity)

        return incident

    @app.get("/api/v1/incidents/{incident_id}", response_model=Incident)
    async def get_incident(
        incident_id: Identifier,
        incident_repo: IncidentRepository = Depends(get_incident_repo),
    ) -> Incident:
        """Get incident by ID."""
        incident = await incident_repo.find_by_id(incident_id)
        if not incident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

        return incident

    @app.patch("/api/v1/incidents/{incident_id}", response_model=Incident)
    async def update_incident(
        incident_id: Identifier,
        request: IncidentUpdateRequest,
        incident_repo: IncidentRepository = Depends(get_incident_repo),
        audit_repo: AuditRepository = Depends(get_audit_repo),
    ) -> Incident:
        """Update incident status or details."""
        incident = await incident_repo.find_by_id(incident_id)
        if not incident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

        # Apply updates
        now = datetime.now(tz=UTC)
        changes = {}

        if request.status:
            old_status = incident.status
            incident.status = request.status
            changes["status"] = {"old": old_status.value, "new": request.status.value}

            # Update timestamps based on status
            if request.status == IncidentStatus.ACKNOWLEDGED and not incident.acknowledged_at:
                incident.acknowledged_at = now
            elif request.status == IncidentStatus.MITIGATING and not incident.mitigated_at:
                incident.mitigated_at = now
            elif request.status == IncidentStatus.RESOLVED and not incident.resolved_at:
                incident.resolved_at = now
            elif request.status == IncidentStatus.CLOSED and not incident.closed_at:
                incident.closed_at = now

        if request.resolution_summary:
            incident.resolution_summary = request.resolution_summary
            changes["resolution_summary"] = "updated"

        if request.post_incident_notes:
            incident.post_incident_notes = request.post_incident_notes
            changes["post_incident_notes"] = "updated"

        # Save changes
        await incident_repo.save(incident)

        # Audit log
        audit_entry = AuditEntry(
            audit_id=f"audit-incident-update-{incident_id}-{now.strftime('%Y%m%d%H%M%S')}",
            timestamp=now,
            actor_type=ActorType.AGENT,
            actor_id="incident-api",
            action="incident.update",
            resource_type="incident",
            resource_id=incident_id,
            outcome="success",
            details=changes,
        )
        await audit_repo.append(audit_entry)

        logger.info("Updated incident %s: %s", incident_id, changes)

        return incident

    @app.get("/api/v1/incidents", response_model=IncidentListResponse)
    async def list_incidents(
        status: IncidentStatus | None = Query(None, description="Filter by status"),
        service_name: str | None = Query(None, description="Filter by service name"),
        environment: str | None = Query(None, description="Filter by environment"),
        limit: int = Query(100, ge=1, le=1000, description="Max results"),
        incident_repo: IncidentRepository = Depends(get_incident_repo),
    ) -> IncidentListResponse:
        """List incidents with optional filters."""
        if status:
            incidents = await incident_repo.find_by_status(status.value, limit=limit)
        elif service_name and environment:
            incidents = await incident_repo.find_by_service(service_name, environment, limit=limit)
        else:
            incidents = await incident_repo.find_open_incidents(limit=limit)

        return IncidentListResponse(incidents=incidents, total=len(incidents))

    @app.post("/api/v1/incidents/{incident_id}/evidence", status_code=status.HTTP_201_CREATED)
    async def attach_evidence(
        incident_id: Identifier,
        request: EvidenceAttachRequest,
        incident_repo: IncidentRepository = Depends(get_incident_repo),
        evidence_repo: EvidenceRepository = Depends(get_evidence_repo),
        audit_repo: AuditRepository = Depends(get_audit_repo),
    ) -> Evidence:
        """Attach evidence to an incident."""
        # Verify incident exists
        incident = await incident_repo.find_by_id(incident_id)
        if not incident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

        # Link evidence to incident
        evidence = request.evidence
        evidence.incident_id = incident_id

        # Save evidence
        await evidence_repo.save(evidence)

        # Audit log
        now = datetime.now(tz=UTC)
        audit_entry = AuditEntry(
            audit_id=f"audit-evidence-{evidence.evidence_id}-{now.strftime('%Y%m%d%H%M%S')}",
            timestamp=now,
            actor_type=ActorType.AGENT,
            actor_id="evidence-collector",
            action="evidence.attach",
            resource_type="evidence",
            resource_id=evidence.evidence_id,
            outcome="success",
            details={
                "incident_id": incident_id,
                "kind": evidence.kind.value,
                "collector": evidence.collector.value,
            },
        )
        await audit_repo.append(audit_entry)

        logger.info("Attached evidence %s to incident %s", evidence.evidence_id, incident_id)

        return evidence

    @app.get("/api/v1/incidents/{incident_id}/evidence", response_model=EvidenceListResponse)
    async def list_incident_evidence(
        incident_id: Identifier,
        evidence_repo: EvidenceRepository = Depends(get_evidence_repo),
    ) -> EvidenceListResponse:
        """List all evidence for an incident."""
        evidence_list = await evidence_repo.find_by_incident(incident_id)

        return EvidenceListResponse(evidence=evidence_list, total=len(evidence_list))

    @app.get("/api/v1/evidence/{evidence_id}", response_model=Evidence)
    async def get_evidence(
        evidence_id: Identifier,
        evidence_repo: EvidenceRepository = Depends(get_evidence_repo),
    ) -> Evidence:
        """Get evidence by ID."""
        evidence = await evidence_repo.find_by_id(evidence_id)
        if not evidence:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")

        return evidence

    # Lifecycle state machine endpoints

    @app.post("/api/v1/incidents/{incident_id}/acknowledge", response_model=Incident)
    async def acknowledge_incident(
        incident_id: Identifier,
        incident_repo: IncidentRepository = Depends(get_incident_repo),
        audit_repo: AuditRepository = Depends(get_audit_repo),
    ) -> Incident:
        """Acknowledge an incident (state transition: OPEN → ACKNOWLEDGED)."""
        incident = await incident_repo.find_by_id(incident_id)
        if not incident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

        if incident.status != IncidentStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot acknowledge incident in {incident.status} state",
            )

        now = datetime.now(tz=UTC)
        incident.status = IncidentStatus.ACKNOWLEDGED
        incident.acknowledged_at = now
        await incident_repo.save(incident)

        audit_entry = AuditEntry(
            audit_id=f"audit-acknowledge-{incident_id}-{now.strftime('%Y%m%d%H%M%S')}",
            timestamp=now,
            actor_type=ActorType.HUMAN,
            actor_id="sre-on-call",
            action="incident.acknowledge",
            resource_type="incident",
            resource_id=incident_id,
            outcome="success",
            details={"status_change": "OPEN → ACKNOWLEDGED"},
        )
        await audit_repo.append(audit_entry)

        logger.info("Acknowledged incident %s", incident_id)
        return incident

    @app.post("/api/v1/incidents/{incident_id}/investigate", response_model=Incident)
    async def start_investigation(
        incident_id: Identifier,
        incident_repo: IncidentRepository = Depends(get_incident_repo),
        audit_repo: AuditRepository = Depends(get_audit_repo),
    ) -> Incident:
        """Start investigation (state transition: ACKNOWLEDGED → INVESTIGATING)."""
        incident = await incident_repo.find_by_id(incident_id)
        if not incident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

        if incident.status != IncidentStatus.ACKNOWLEDGED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot start investigation from {incident.status} state",
            )

        now = datetime.now(tz=UTC)
        incident.status = IncidentStatus.INVESTIGATING
        await incident_repo.save(incident)

        audit_entry = AuditEntry(
            audit_id=f"audit-investigate-{incident_id}-{now.strftime('%Y%m%d%H%M%S')}",
            timestamp=now,
            actor_type=ActorType.AGENT,
            actor_id="incident-agent",
            action="incident.investigate",
            resource_type="incident",
            resource_id=incident_id,
            outcome="success",
            details={"status_change": "ACKNOWLEDGED → INVESTIGATING"},
        )
        await audit_repo.append(audit_entry)

        logger.info("Started investigation for incident %s", incident_id)
        return incident

    @app.post("/api/v1/incidents/{incident_id}/mitigate", response_model=Incident)
    async def start_mitigation(
        incident_id: Identifier,
        incident_repo: IncidentRepository = Depends(get_incident_repo),
        audit_repo: AuditRepository = Depends(get_audit_repo),
    ) -> Incident:
        """Start mitigation (state transition: INVESTIGATING → MITIGATING)."""
        incident = await incident_repo.find_by_id(incident_id)
        if not incident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

        if incident.status != IncidentStatus.INVESTIGATING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot start mitigation from {incident.status} state",
            )

        now = datetime.now(tz=UTC)
        incident.status = IncidentStatus.MITIGATING
        incident.mitigated_at = now
        await incident_repo.save(incident)

        audit_entry = AuditEntry(
            audit_id=f"audit-mitigate-{incident_id}-{now.strftime('%Y%m%d%H%M%S')}",
            timestamp=now,
            actor_type=ActorType.AGENT,
            actor_id="remediation-agent",
            action="incident.mitigate",
            resource_type="incident",
            resource_id=incident_id,
            outcome="success",
            details={"status_change": "INVESTIGATING → MITIGATING"},
        )
        await audit_repo.append(audit_entry)

        logger.info("Started mitigation for incident %s", incident_id)
        return incident

    @app.post("/api/v1/incidents/{incident_id}/resolve", response_model=Incident)
    async def resolve_incident(
        incident_id: Identifier,
        request: IncidentUpdateRequest,
        incident_repo: IncidentRepository = Depends(get_incident_repo),
        audit_repo: AuditRepository = Depends(get_audit_repo),
    ) -> Incident:
        """Resolve an incident (state transition: MITIGATING → RESOLVED)."""
        incident = await incident_repo.find_by_id(incident_id)
        if not incident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

        if incident.status != IncidentStatus.MITIGATING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resolve incident from {incident.status} state",
            )

        now = datetime.now(tz=UTC)
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = now
        if request.resolution_summary:
            incident.resolution_summary = request.resolution_summary
        await incident_repo.save(incident)

        audit_entry = AuditEntry(
            audit_id=f"audit-resolve-{incident_id}-{now.strftime('%Y%m%d%H%M%S')}",
            timestamp=now,
            actor_type=ActorType.HUMAN,
            actor_id="sre-on-call",
            action="incident.resolve",
            resource_type="incident",
            resource_id=incident_id,
            outcome="success",
            details={"status_change": "MITIGATING → RESOLVED"},
        )
        await audit_repo.append(audit_entry)

        logger.info("Resolved incident %s", incident_id)
        return incident

    @app.post("/api/v1/incidents/{incident_id}/reopen", response_model=Incident)
    async def reopen_incident(
        incident_id: Identifier,
        incident_repo: IncidentRepository = Depends(get_incident_repo),
        audit_repo: AuditRepository = Depends(get_audit_repo),
    ) -> Incident:
        """Reopen an incident (state transition: RESOLVED/CLOSED → OPEN)."""
        incident = await incident_repo.find_by_id(incident_id)
        if not incident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

        if incident.status not in [IncidentStatus.RESOLVED, IncidentStatus.CLOSED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reopen incident from {incident.status} state",
            )

        now = datetime.now(tz=UTC)
        old_status = incident.status
        incident.status = IncidentStatus.OPEN
        await incident_repo.save(incident)

        audit_entry = AuditEntry(
            audit_id=f"audit-reopen-{incident_id}-{now.strftime('%Y%m%d%H%M%S')}",
            timestamp=now,
            actor_type=ActorType.HUMAN,
            actor_id="sre-on-call",
            action="incident.reopen",
            resource_type="incident",
            resource_id=incident_id,
            outcome="success",
            details={"status_change": f"{old_status.value} → OPEN"},
        )
        await audit_repo.append(audit_entry)

        logger.info("Reopened incident %s", incident_id)
        return incident

    @app.post("/api/v1/incidents/{incident_id}/close", response_model=Incident)
    async def close_incident(
        incident_id: Identifier,
        request: IncidentUpdateRequest,
        incident_repo: IncidentRepository = Depends(get_incident_repo),
        audit_repo: AuditRepository = Depends(get_audit_repo),
    ) -> Incident:
        """Close an incident (state transition: RESOLVED → CLOSED)."""
        incident = await incident_repo.find_by_id(incident_id)
        if not incident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

        if incident.status != IncidentStatus.RESOLVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot close incident from {incident.status} state (must be RESOLVED)",
            )

        now = datetime.now(tz=UTC)
        incident.status = IncidentStatus.CLOSED
        incident.closed_at = now
        if request.post_incident_notes:
            incident.post_incident_notes = request.post_incident_notes
        await incident_repo.save(incident)

        audit_entry = AuditEntry(
            audit_id=f"audit-close-{incident_id}-{now.strftime('%Y%m%d%H%M%S')}",
            timestamp=now,
            actor_type=ActorType.HUMAN,
            actor_id="sre-on-call",
            action="incident.close",
            resource_type="incident",
            resource_id=incident_id,
            outcome="success",
            details={"status_change": "RESOLVED → CLOSED"},
        )
        await audit_repo.append(audit_entry)

        logger.info("Closed incident %s", incident_id)
        return incident

    @app.get("/health")
    async def health_check() -> dict:
        """Health check endpoint."""
        return {"status": "healthy", "service": "incident-api"}

    return app
