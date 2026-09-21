"""SQLAlchemy implementation of repositories and unit of work."""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import Any

from sqlalchemy import (
    Table,
    and_,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.contracts.common import Environment, Identifier, ServiceRef
from packages.contracts.incidents import Incident, IncidentStatus, Severity
from packages.persistence.repositories import (
    IncidentRepository,
)
from packages.persistence.unit_of_work import UnitOfWork


class SqlAlchemyIncidentRepository(IncidentRepository):
    """SQLAlchemy implementation of incident repository."""

    def __init__(self, conn: AsyncConnection, table: Table) -> None:
        self.conn = conn
        self.table = table

    async def save(self, incident: Incident) -> None:
        """Persist incident using upsert."""
        values = {
            "incident_id": incident.incident_id,
            "title": incident.title,
            "severity": incident.severity.value,
            "status": incident.status.value,
            "service_name": incident.service.name,
            "service_environment": incident.service.environment.value,
            "service_namespace": incident.service.namespace,
            "detected_at": incident.detected_at,
            "opened_at": incident.opened_at,
            "acknowledged_at": incident.acknowledged_at,
            "mitigated_at": incident.mitigated_at,
            "resolved_at": incident.resolved_at,
            "closed_at": incident.closed_at,
            "confidence": int(incident.confidence * 100) if incident.confidence else None,
            "resolution_summary": incident.resolution_summary,
            "post_incident_notes": incident.post_incident_notes,
            "correlation_id": incident.correlation_id,
            "updated_at": datetime.now(tz=UTC),
        }

        stmt = insert(self.table).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["incident_id"],
            set_={k: v for k, v in values.items() if k != "incident_id"},
        )

        await self.conn.execute(stmt)

    async def find_by_id(self, incident_id: Identifier) -> Incident | None:
        """Retrieve incident by ID."""
        stmt = select(self.table).where(self.table.c.incident_id == incident_id)
        result = await self.conn.execute(stmt)
        row = result.fetchone()

        return self._row_to_incident(row) if row else None

    async def find_by_service(
        self, service_name: str, environment: str, limit: int = 100
    ) -> list[Incident]:
        """Find incidents for a service."""
        stmt = (
            select(self.table)
            .where(
                and_(
                    self.table.c.service_name == service_name,
                    self.table.c.service_environment == environment,
                )
            )
            .order_by(self.table.c.opened_at.desc())
            .limit(limit)
        )

        result = await self.conn.execute(stmt)
        return [self._row_to_incident(row) for row in result.fetchall()]

    async def find_by_status(self, status: str, limit: int = 100) -> list[Incident]:
        """Find incidents by status."""
        stmt = (
            select(self.table)
            .where(self.table.c.status == status)
            .order_by(self.table.c.opened_at.desc())
            .limit(limit)
        )

        result = await self.conn.execute(stmt)
        return [self._row_to_incident(row) for row in result.fetchall()]

    async def find_open_incidents(self, limit: int = 100) -> list[Incident]:
        """Find all open or in-progress incidents."""
        open_statuses = ["open", "acknowledged", "investigating", "mitigating", "reopened"]
        stmt = (
            select(self.table)
            .where(self.table.c.status.in_(open_statuses))
            .order_by(self.table.c.opened_at.desc())
            .limit(limit)
        )

        result = await self.conn.execute(stmt)
        return [self._row_to_incident(row) for row in result.fetchall()]

    def _row_to_incident(self, row: Any) -> Incident:
        """Convert database row to Incident."""
        return Incident(
            incident_id=row.incident_id,
            title=row.title,
            severity=Severity(row.severity),
            service=ServiceRef(
                name=row.service_name,
                environment=Environment(row.service_environment),
                namespace=row.service_namespace,
            ),
            status=IncidentStatus(row.status),
            detected_at=row.detected_at,
            opened_at=row.opened_at,
            acknowledged_at=row.acknowledged_at,
            mitigated_at=row.mitigated_at,
            resolved_at=row.resolved_at,
            closed_at=row.closed_at,
            confidence=row.confidence / 100.0 if row.confidence else None,
            resolution_summary=row.resolution_summary,
            post_incident_notes=row.post_incident_notes,
            correlation_id=row.correlation_id,
        )


class SqlAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy implementation of Unit of Work."""

    def __init__(self, conn: AsyncConnection, tables: dict[str, Table]) -> None:
        self.conn = conn
        self.incidents = SqlAlchemyIncidentRepository(conn, tables["incidents"])
        # Evidence, Remediation, Audit repos would be initialized similarly

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        """Begin transaction (already begun by connection context)."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Rollback on exception."""
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        """Commit the transaction."""
        await self.conn.commit()

    async def rollback(self) -> None:
        """Rollback the transaction."""
        await self.conn.rollback()
