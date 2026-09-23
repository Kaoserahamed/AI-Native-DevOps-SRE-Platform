"""Persistence layer with repository pattern and transaction boundaries.

Keeps SQL and data access logic separate from business logic through clean interfaces.
"""

from __future__ import annotations

__all__ = [
    "AsyncAuditWriter",
    "AuditChainError",
    "AuditRepository",
    "EvidenceRepository",
    "IdempotencyRepository",
    "IncidentRepository",
    "RemediationRepository",
    "SqlAlchemyAuditRepository",
    "SqlAlchemyEvidenceRepository",
    "SqlAlchemyIncidentRepository",
    "SqlAlchemyRemediationRepository",
    "SqlAlchemyUnitOfWork",
    "UnitOfWork",
]

from packages.persistence.audit_writer import AsyncAuditWriter, AuditChainError
from packages.persistence.repositories import (
    AuditRepository,
    EvidenceRepository,
    IdempotencyRepository,
    IncidentRepository,
    RemediationRepository,
)
from packages.persistence.sqlalchemy_impl import (
    SqlAlchemyAuditRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyIncidentRepository,
    SqlAlchemyRemediationRepository,
    SqlAlchemyUnitOfWork,
)
from packages.persistence.unit_of_work import UnitOfWork
