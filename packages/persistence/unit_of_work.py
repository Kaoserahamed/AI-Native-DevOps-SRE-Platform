"""Unit of Work pattern for transaction boundaries.

Manages database transactions and provides access to repositories within
a transactional context.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol

from packages.persistence.repositories import (
    AuditRepository,
    EvidenceRepository,
    IdempotencyRepository,
    IncidentRepository,
    RemediationRepository,
)


class UnitOfWork(Protocol):
    """Unit of Work manages a transaction boundary.

    Usage:
        async with uow:
            incident = await uow.incidents.find_by_id(id)
            incident.status = "resolved"
            await uow.incidents.save(incident)
            await uow.commit()
    """

    incidents: IncidentRepository
    evidence: EvidenceRepository
    remediation: RemediationRepository
    audit: AuditRepository
    idempotency: IdempotencyRepository

    async def __aenter__(self) -> UnitOfWork:
        """Begin transaction."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Rollback transaction on exception, otherwise no-op."""
        ...

    async def commit(self) -> None:
        """Commit the current transaction."""
        ...

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        ...
