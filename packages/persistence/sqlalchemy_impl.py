"""SQLAlchemy implementations of the repository contracts.

Every repository in this module shares one connection with the rest of its unit of work, which is what
makes a lifecycle transition atomic: an incident update and the audit event that records it are
committed together or not at all (see :class:`SqlAlchemyUnitOfWork`).

Two properties are deliberate:

* **One schema definition.** The tables come from :mod:`packages.persistence.tables`, the same
  definition the migrations create. A repository never re-declares a column.
* **Portable SQL.** The deployed engine is PostgreSQL and the test suite runs on SQLite, so the only
  dialect-specific code is the upsert: each engine needs its own ``insert`` construct. Everything else
  is Core SQL that both engines execute identically.

The ``document`` column holds the authoritative contract payload for each row, so a repository reads
back exactly what the contract validated on write; the scalar columns beside it are the queryable
projection (status, service, timestamps) that indexes and operator queries work on.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from types import TracebackType
from typing import Any

from sqlalchemy import Table, and_, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.contracts.audit import AuditEvent
from packages.contracts.common import (
    Environment,
    Identifier,
    PlatformModel,
    ServiceRef,
    Severity,
)
from packages.contracts.evidence import Evidence, EvidenceCollector, EvidenceKind, TimeWindow
from packages.contracts.incidents import Incident, IncidentStatus
from packages.contracts.remediation import Approval, RemediationProposal
from packages.persistence import tables
from packages.persistence.repositories import (
    AuditRepository,
    EvidenceRepository,
    IncidentRepository,
    RemediationRepository,
)
from packages.persistence.unit_of_work import UnitOfWork

#: Incident statuses that count as open for :meth:`SqlAlchemyIncidentRepository.find_open_incidents`.
OPEN_STATUSES: tuple[str, ...] = ("open", "acknowledged", "investigating", "mitigating", "reopened")


def _document(model: PlatformModel) -> dict[str, Any]:
    """Return the JSON representation of a contract payload, stored verbatim in ``document``."""
    return model.model_dump(mode="json", exclude_computed_fields=True)


def _insert(conn: AsyncConnection, table: Table) -> Any:
    """Return the dialect ``insert`` construct able to express an upsert on this connection."""
    dialect = conn.dialect.name
    if dialect == "postgresql":  # pragma: no cover - exercised by the integration suite
        return postgresql.insert(table)
    if dialect == "sqlite":
        return sqlite.insert(table)
    raise NotImplementedError(f"upsert is not implemented for dialect {dialect!r}")


def _upsert(
    conn: AsyncConnection,
    table: Table,
    values: Mapping[str, Any],
    conflict_columns: tuple[str, ...],
) -> Any:
    """Return an upsert statement that updates every supplied column on conflict."""
    statement = _insert(conn, table).values(**values)
    return statement.on_conflict_do_update(
        index_elements=list(conflict_columns),
        set_={key: value for key, value in values.items() if key not in conflict_columns},
    )


class SqlAlchemyIncidentRepository(IncidentRepository):
    """SQLAlchemy implementation of the incident repository."""

    def __init__(self, conn: AsyncConnection, table: Table | None = None) -> None:
        self.conn = conn
        self.table = table if table is not None else tables.incidents

    async def save(self, incident: Incident) -> None:
        """Persist an incident, inserting it or updating the existing row."""
        now = datetime.now(tz=UTC)
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
            "document": _document(incident),
            "updated_at": now,
        }
        if await self.find_by_id(incident.incident_id) is None:
            values["created_at"] = now
        await self.conn.execute(_upsert(self.conn, self.table, values, ("incident_id",)))

    async def find_by_id(self, incident_id: Identifier) -> Incident | None:
        """Retrieve incident by ID."""
        statement = select(self.table).where(self.table.c.incident_id == incident_id)
        row = (await self.conn.execute(statement)).fetchone()
        return self._row_to_incident(row) if row else None

    async def find_by_service(
        self, service_name: str, environment: str, limit: int = 100
    ) -> list[Incident]:
        """Find incidents for a service in one environment."""
        statement = (
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
        rows = (await self.conn.execute(statement)).fetchall()
        return [self._row_to_incident(row) for row in rows]

    async def find_by_status(self, status: str, limit: int = 100) -> list[Incident]:
        """Find incidents by status."""
        statement = (
            select(self.table)
            .where(self.table.c.status == status)
            .order_by(self.table.c.opened_at.desc())
            .limit(limit)
        )
        rows = (await self.conn.execute(statement)).fetchall()
        return [self._row_to_incident(row) for row in rows]

    async def find_open_incidents(self, limit: int = 100) -> list[Incident]:
        """Find all incidents that have not been resolved or closed."""
        statement = (
            select(self.table)
            .where(self.table.c.status.in_(OPEN_STATUSES))
            .order_by(self.table.c.opened_at.desc())
            .limit(limit)
        )
        rows = (await self.conn.execute(statement)).fetchall()
        return [self._row_to_incident(row) for row in rows]

    def _row_to_incident(self, row: Any) -> Incident:
        """Return the contract payload the row was written from, or rebuild it from the columns."""
        if row.document is not None:
            return Incident.model_validate(row.document)
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


class SqlAlchemyEvidenceRepository(EvidenceRepository):
    """SQLAlchemy implementation of the evidence repository."""

    def __init__(self, conn: AsyncConnection, table: Table | None = None) -> None:
        self.conn = conn
        self.table = table if table is not None else tables.evidence

    async def save(self, evidence: Evidence) -> None:
        """Persist an evidence item, inserting it or updating the existing row."""
        values = {
            "evidence_id": evidence.evidence_id,
            "kind": evidence.kind.value,
            "collector": evidence.collector.value,
            "collected_at": evidence.collected_at,
            "summary": evidence.summary,
            "service_name": evidence.service.name if evidence.service else None,
            "service_environment": (
                evidence.service.environment.value if evidence.service else None
            ),
            "service_namespace": evidence.service.namespace if evidence.service else None,
            "window_start": evidence.window.start if evidence.window else None,
            "window_end": evidence.window.end if evidence.window else None,
            "incident_id": evidence.incident_id,
            "correlation_id": evidence.correlation_id,
            "document": _document(evidence),
            "created_at": datetime.now(tz=UTC),
        }
        await self.conn.execute(_upsert(self.conn, self.table, values, ("evidence_id",)))

    async def find_by_id(self, evidence_id: Identifier) -> Evidence | None:
        """Retrieve evidence by ID."""
        statement = select(self.table).where(self.table.c.evidence_id == evidence_id)
        row = (await self.conn.execute(statement)).fetchone()
        return self._row_to_evidence(row) if row else None

    async def find_by_incident(self, incident_id: Identifier) -> list[Evidence]:
        """Find all evidence attached to an incident, newest first."""
        statement = (
            select(self.table)
            .where(self.table.c.incident_id == incident_id)
            .order_by(self.table.c.collected_at.desc())
        )
        rows = (await self.conn.execute(statement)).fetchall()
        return [self._row_to_evidence(row) for row in rows]

    async def find_recent(
        self, service_name: str | None = None, limit: int = 100
    ) -> list[Evidence]:
        """Find recent evidence, optionally filtered by service."""
        statement = select(self.table).order_by(self.table.c.collected_at.desc()).limit(limit)
        if service_name is not None:
            statement = statement.where(self.table.c.service_name == service_name)
        rows = (await self.conn.execute(statement)).fetchall()
        return [self._row_to_evidence(row) for row in rows]

    def _row_to_evidence(self, row: Any) -> Evidence:
        """Return the stored payload, or rebuild an equivalent item from the columns.

        A row written by a narrower writer carries no ``document``; the summary is then the only text
        available, so it is used as the excerpt. Rows written by this repository round-trip exactly.
        """
        if row.document is not None:
            return Evidence.model_validate(row.document)
        window = (
            TimeWindow(start=row.window_start, end=row.window_end)
            if row.window_start is not None and row.window_end is not None
            else None
        )
        service = (
            ServiceRef(
                name=row.service_name,
                environment=Environment(row.service_environment),
                namespace=row.service_namespace,
            )
            if row.service_name is not None and row.service_environment is not None
            else None
        )
        return Evidence(
            evidence_id=row.evidence_id,
            kind=EvidenceKind(row.kind),
            collector=EvidenceCollector(row.collector),
            collected_at=row.collected_at,
            summary=row.summary,
            service=service,
            window=window,
            excerpt=row.summary,
            incident_id=row.incident_id,
            correlation_id=row.correlation_id,
        )


class SqlAlchemyRemediationRepository(RemediationRepository):
    """SQLAlchemy implementation of the remediation proposal and approval repository."""

    def __init__(
        self,
        conn: AsyncConnection,
        proposals_table: Table | None = None,
        approvals_table: Table | None = None,
    ) -> None:
        self.conn = conn
        self.proposals = proposals_table if proposals_table is not None else tables.remediation_proposals
        self.approvals = approvals_table if approvals_table is not None else tables.approvals

    async def save_proposal(self, proposal: RemediationProposal) -> None:
        """Persist a remediation proposal."""
        values = {
            "proposal_id": proposal.proposal_id,
            "incident_id": proposal.incident_id,
            "category": proposal.category.value,
            "risk": proposal.risk.value,
                        "confidence": round(proposal.confidence * 100),
            "created_at": proposal.created_at,
            "expires_at": proposal.expires_at,
            "document": _document(proposal),
        }
        await self.conn.execute(_upsert(self.conn, self.proposals, values, ("proposal_id",)))

    async def save_approval(self, approval: Approval) -> None:
        """Persist an approval decision."""
        values = {
            "approval_id": approval.approval_id,
            "proposal_id": approval.proposal_id,
            "incident_id": approval.incident_id,
            "action_hash": approval.action_hash,
            "decision": approval.decision.value,
            "approver": approval.approver.identity,
            "decided_at": approval.decided_at,
            "expires_at": approval.expires_at,
            "consumed_at": approval.consumed_at,
            "document": _document(approval),
        }
        await self.conn.execute(_upsert(self.conn, self.approvals, values, ("approval_id",)))

    async def find_proposal_by_id(self, proposal_id: Identifier) -> RemediationProposal | None:
        """Retrieve a proposal by ID."""
        statement = select(self.proposals).where(self.proposals.c.proposal_id == proposal_id)
        row = (await self.conn.execute(statement)).fetchone()
        return RemediationProposal.model_validate(row.document) if row else None

    async def find_approval_by_id(self, approval_id: Identifier) -> Approval | None:
        """Retrieve an approval by ID."""
        statement = select(self.approvals).where(self.approvals.c.approval_id == approval_id)
        row = (await self.conn.execute(statement)).fetchone()
        return Approval.model_validate(row.document) if row else None

    async def find_proposals_by_incident(
        self, incident_id: Identifier
    ) -> list[RemediationProposal]:
        """Find every proposal raised for one incident, newest first."""
        statement = (
            select(self.proposals)
            .where(self.proposals.c.incident_id == incident_id)
            .order_by(self.proposals.c.created_at.desc())
        )
        rows = (await self.conn.execute(statement)).fetchall()
        return [RemediationProposal.model_validate(row.document) for row in rows]

    async def find_pending_approvals(self, before: datetime) -> list[Approval]:
        """Find approvals that authorise an action but expire before ``before``."""
        statement = (
            select(self.approvals)
            .where(
                and_(
                    self.approvals.c.decision == "approved",
                    self.approvals.c.consumed_at.is_(None),
                    self.approvals.c.expires_at <= before,
                )
            )
            .order_by(self.approvals.c.expires_at.asc())
        )
        rows = (await self.conn.execute(statement)).fetchall()
        return [Approval.model_validate(row.document) for row in rows]


class SqlAlchemyAuditRepository(AuditRepository):
    """Append-only SQLAlchemy implementation of the audit repository.

    Two rules make the trail trustworthy and both are enforced here rather than trusted to callers:
    a stored event is never updated (``append`` performs an insert, never an upsert), and every event
    carries the digest of the event before it. A caller that supplies a ``previous_digest`` which does
    not match the stored head is refused instead of being allowed to fork the chain.
    """

    def __init__(self, conn: AsyncConnection, table: Table | None = None) -> None:
        self.conn = conn
        self.table = table if table is not None else tables.audit_events

    async def append(self, event: AuditEvent) -> AuditEvent:
        """Append an audit event, sealing it onto the stored chain, and return the stored record."""
        head = await self.head()
        expected = head.digest if head is not None else None

        if event.previous_digest is not None and event.previous_digest != expected:
            raise ValueError(
                "audit event does not chain onto the stored head: expected "
                f"{expected!r}, got {event.previous_digest!r}"
            )

        sealed = (
            event
            if event.previous_digest == expected
            else event.model_copy(update={"previous_digest": expected})
        )
        await self.conn.execute(
            self.table.insert().values(
                event_id=sealed.event_id,
                occurred_at=sealed.occurred_at,
                actor_type=sealed.actor.actor_type.value,
                actor_id=sealed.actor.actor_id,
                event_type=sealed.event_type.value,
                subject=sealed.subject,
                result=sealed.result.value,
                correlation_id=sealed.correlation_id,
                incident_id=sealed.incident_id,
                approval_id=sealed.approval_id,
                action_hash=sealed.action_hash,
                tool=sealed.tool,
                document=_document(sealed),
                previous_digest=sealed.previous_digest,
                digest=sealed.digest,
                created_at=datetime.now(tz=UTC),
            )
        )
        return sealed

    async def head(self) -> AuditEvent | None:
        """Return the most recently appended event, or ``None`` when the trail is empty."""
        statement = select(self.table).order_by(self.table.c.id.desc()).limit(1)
        row = (await self.conn.execute(statement)).fetchone()
        return AuditEvent.model_validate(row.document) if row else None

    async def find_oldest_first(self, limit: int = 100) -> list[AuditEvent]:
        """Find stored events oldest first, so the hash chain can be re-walked."""
        statement = select(self.table).order_by(self.table.c.id.asc()).limit(limit)
        rows = (await self.conn.execute(statement)).fetchall()
        return [AuditEvent.model_validate(row.document) for row in rows]

    async def find_by_subject(self, subject: Identifier, limit: int = 100) -> list[AuditEvent]:
        """Find audit events about one subject."""
        return await self._find_newest_first(self.table.c.subject == subject, limit)

    async def find_by_incident(self, incident_id: Identifier, limit: int = 100) -> list[AuditEvent]:
        """Find audit events recorded against one incident."""
        return await self._find_newest_first(self.table.c.incident_id == incident_id, limit)

    async def find_by_actor(self, actor_id: str, limit: int = 100) -> list[AuditEvent]:
        """Find audit events by actor."""
        return await self._find_newest_first(self.table.c.actor_id == actor_id, limit)

    async def find_recent(self, limit: int = 100) -> list[AuditEvent]:
        """Find recent audit events, newest first."""
        statement = select(self.table).order_by(self.table.c.id.desc()).limit(limit)
        rows = (await self.conn.execute(statement)).fetchall()
        return [AuditEvent.model_validate(row.document) for row in rows]

    async def _find_newest_first(self, predicate: Any, limit: int) -> list[AuditEvent]:
        """Return events matching ``predicate``, newest first."""
        statement = (
            select(self.table).where(predicate).order_by(self.table.c.id.desc()).limit(limit)
        )
        rows = (await self.conn.execute(statement)).fetchall()
        return [AuditEvent.model_validate(row.document) for row in rows]


class SqlAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy unit of work: one connection, one transaction, every repository.

    The connection owns the transaction, so a caller that writes several aggregates and then commits
    gets all of them or none: an incident transition and the audit event describing it cannot be torn
    apart by a crash between two statements.

    ``idempotency`` is deliberately absent — the idempotency contract is served by the job queue's
    Redis keys (``packages.job_queue``) rather than by this relational schema, so implementing it here
    would create a second, competing source of truth.
    """

    def __init__(
        self, conn: AsyncConnection, tables_by_name: Mapping[str, Table] | None = None
    ) -> None:
        available = dict(tables_by_name or {})
        self.conn = conn
        self.incidents = SqlAlchemyIncidentRepository(conn, available.get("incidents"))
        self.evidence = SqlAlchemyEvidenceRepository(conn, available.get("evidence"))
        self.remediation = SqlAlchemyRemediationRepository(
            conn,
            available.get("remediation_proposals"),
            available.get("approvals"),
        )
        self.audit = SqlAlchemyAuditRepository(conn, available.get("audit_events"))

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        """Enter the transaction (the connection context already began it)."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Roll back on exception so a failed request cannot leave a partial write behind."""
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        """Commit the transaction."""
        await self.conn.commit()

    async def rollback(self) -> None:
        """Roll back the transaction."""
        await self.conn.rollback()

