"""Repository interfaces for database access.

Each repository provides a bounded interface for a specific aggregate root,
hiding SQL details from business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from packages.contracts.audit import AuditEvent
from packages.contracts.common import Identifier
from packages.contracts.evidence import Evidence
from packages.contracts.incidents import Incident
from packages.contracts.remediation import Approval, RemediationProposal


class IncidentRepository(ABC):
    """Repository for incident aggregate operations."""

    @abstractmethod
    async def save(self, incident: Incident) -> None:
        """Persist an incident (insert or update)."""
        ...

    @abstractmethod
    async def find_by_id(self, incident_id: Identifier) -> Incident | None:
        """Retrieve incident by ID."""
        ...

    @abstractmethod
    async def find_by_service(
        self, service_name: str, environment: str, limit: int = 100
    ) -> list[Incident]:
        """Find incidents for a service."""
        ...

    @abstractmethod
    async def find_by_status(self, status: str, limit: int = 100) -> list[Incident]:
        """Find incidents by status."""
        ...

    @abstractmethod
    async def find_open_incidents(self, limit: int = 100) -> list[Incident]:
        """Find all open or in-progress incidents."""
        ...


class EvidenceRepository(ABC):
    """Repository for evidence items."""

    @abstractmethod
    async def save(self, evidence: Evidence) -> None:
        """Persist evidence."""
        ...

    @abstractmethod
    async def find_by_id(self, evidence_id: Identifier) -> Evidence | None:
        """Retrieve evidence by ID."""
        ...

    @abstractmethod
    async def find_by_incident(self, incident_id: Identifier) -> list[Evidence]:
        """Find all evidence for an incident."""
        ...

    @abstractmethod
    async def find_recent(
        self, service_name: str | None = None, limit: int = 100
    ) -> list[Evidence]:
        """Find recent evidence, optionally filtered by service."""
        ...


class RemediationRepository(ABC):
    """Repository for remediation proposals and approvals."""

    @abstractmethod
    async def save_proposal(self, proposal: RemediationProposal) -> None:
        """Persist a remediation proposal."""
        ...

    @abstractmethod
    async def save_approval(self, approval: Approval) -> None:
        """Persist an approval."""
        ...

    @abstractmethod
    async def find_proposal_by_id(self, proposal_id: Identifier) -> RemediationProposal | None:
        """Retrieve proposal by ID."""
        ...

    @abstractmethod
    async def find_approval_by_id(self, approval_id: Identifier) -> Approval | None:
        """Retrieve approval by ID."""
        ...

    @abstractmethod
    async def find_proposals_by_incident(
        self, incident_id: Identifier
    ) -> list[RemediationProposal]:
        """Find all proposals for an incident."""
        ...

    @abstractmethod
    async def find_pending_approvals(self, before: datetime) -> list[Approval]:
        """Find approvals that expire before the given time."""
        ...


class AuditRepository(ABC):
    """Repository for the append-only audit trail.

    The interface mirrors :class:`packages.governance.audit.AuditLog` in the fields it exposes, but it is
    asynchronous because the trail is stored in the same database as the aggregates it describes. Appending
    returns the stored event: a store that seals an event onto the chain (setting ``previous_digest``)
    reports the sealed record back to the writer rather than leaving the caller with a stale copy.
    """

    @abstractmethod
    async def append(self, event: AuditEvent) -> AuditEvent:
        """Append an audit event (insert-only) and return the stored record."""
        ...

    @abstractmethod
    async def head(self) -> AuditEvent | None:
        """Return the most recent event, or ``None`` when the trail is empty."""
        ...

    @abstractmethod
    async def find_oldest_first(self, limit: int = 100) -> list[AuditEvent]:
        """Find stored events oldest first, so the hash chain can be re-walked."""
        ...

    @abstractmethod
    async def find_by_subject(self, subject: Identifier, limit: int = 100) -> list[AuditEvent]:
        """Find audit events about one subject (an incident id, a proposal id, ...)."""
        ...

    @abstractmethod
    async def find_by_incident(self, incident_id: Identifier, limit: int = 100) -> list[AuditEvent]:
        """Find audit events recorded against one incident."""
        ...

    @abstractmethod
    async def find_by_actor(self, actor_id: str, limit: int = 100) -> list[AuditEvent]:
        """Find audit events by actor."""
        ...

    @abstractmethod
    async def find_recent(self, limit: int = 100) -> list[AuditEvent]:
        """Find recent audit events, newest first."""
        ...


class IdempotencyRepository(ABC):
    """Repository for idempotency key management."""

    @abstractmethod
    async def check_and_lock(
        self, key: Identifier, resource_type: str, ttl_seconds: int = 3600
    ) -> tuple[bool, str | None]:
        """Check if key exists and lock it if not.

        Returns
        -------
        tuple[bool, str | None]
            (is_new, existing_resource_id)
        """
        ...

    @abstractmethod
    async def record_result(
        self,
        key: Identifier,
        resource_id: Identifier,
        response: dict[str, Any] | None = None,
    ) -> None:
        """Record the result for an idempotency key."""
        ...

    @abstractmethod
    async def get_result(self, key: Identifier) -> dict[str, Any] | None:
        """Retrieve cached result for an idempotency key."""
        ...

    @abstractmethod
    async def cleanup_expired(self, before: datetime) -> int:
        """Remove expired idempotency keys. Returns count deleted."""
        ...
