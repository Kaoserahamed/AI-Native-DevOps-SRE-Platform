"""Relational schema for the incident control loop.

The tables are defined once, here, and used by two callers: the migration that creates them
(``migrations/versions/001_initial_schema.py``) and the repositories that read and write them
(``packages.persistence.sqlalchemy_impl``). Defining them twice is how a schema and its data access
drift apart, so there is exactly one definition.

Two rules keep this schema honest about the contract it stores:

* **The columns are the queryable projection.** They are the fields the platform filters, orders or
  reports on — ``status``, ``service_name``, ``collected_at``, ``occurred_at`` — and they are what an
  operator or a database index can work with.
* **The ``document`` column is the authoritative contract payload.** Aggregates carry fields that are
  structured but never queried (an incident's suspected causes, a proposal's rollback plan). Storing
  them as JSON keeps the round trip lossless: what a repository reads back is exactly what the
  contract validated on write.

Types are deliberately portable between PostgreSQL (the deployed engine) and SQLite (the engine the
test suite runs on), so the same code path is exercised in both.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

#: Deterministic constraint names, so a migration diff and a database error both name the same object.
NAMING_CONVENTION: Final[dict[str, str | Callable[..., str]]] = {
    "ix": "ix_%(table_name)s_%(column_names)s",
    "uq": "uq_%(table_name)s_%(column_names)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_names)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
    # ``column_names`` is a custom token: SQLAlchemy 2.0 does not provide it
    # automatically, so we supply a callable that joins the constraint's
    # column names with underscores.  Without this the ``ix``/``uq``/``fk``
    # templates raise ``KeyError`` at import time.
        "column_names": lambda const, _table: "_".join(col.name for col in const.columns),
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)

INCIDENT_STATUSES: Final[tuple[str, ...]] = (
    "open",
    "acknowledged",
    "investigating",
    "mitigating",
    "resolved",
    "reopened",
    "closed",
)
SEVERITIES: Final[tuple[str, ...]] = ("sev1", "sev2", "sev3")
ENVIRONMENTS: Final[tuple[str, ...]] = ("development", "staging", "production")
EVIDENCE_KINDS: Final[tuple[str, ...]] = (
    "metric_series",
    "log_excerpt",
    "trace_summary",
    "kubernetes_object",
    "deployment_event",
    "configuration_diff",
)
AUDIT_ACTOR_TYPES: Final[tuple[str, ...]] = ("human", "agent", "automation", "system")
AUDIT_RESULTS: Final[tuple[str, ...]] = ("succeeded", "failed", "denied")
APPROVAL_DECISIONS: Final[tuple[str, ...]] = ("approved", "rejected")
EXECUTION_STATUSES: Final[tuple[str, ...]] = (
    "running",
    "success",
    "failure",
    "timeout",
    "cancelled",
)

#: Longest value a bounded JSON payload may carry, expressed as a documented policy rather than a guess.
MAX_DOCUMENT_BYTES: Final[int] = 1_048_576


def _sql_in(column: str, values: tuple[str, ...]) -> str:
    """Return a portable ``CHECK`` expression constraining ``column`` to ``values``."""
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


incidents = Table(
    "incidents",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("incident_id", String(128), nullable=False, unique=True, index=True),
    Column("title", String(280), nullable=False),
    Column("severity", String(20), nullable=False),
    Column("status", String(20), nullable=False, index=True),
    Column("service_name", String(64), nullable=False, index=True),
    Column("service_environment", String(20), nullable=False),
    Column("service_namespace", String(64), nullable=True),
    Column("detected_at", DateTime(timezone=True), nullable=False),
    Column("opened_at", DateTime(timezone=True), nullable=False, index=True),
    Column("acknowledged_at", DateTime(timezone=True), nullable=True),
    Column("mitigated_at", DateTime(timezone=True), nullable=True),
    Column("resolved_at", DateTime(timezone=True), nullable=True, index=True),
    Column("closed_at", DateTime(timezone=True), nullable=True),
    Column("confidence", Integer, nullable=True),  # stored as an integer percentage, 0-100
    Column("resolution_summary", Text, nullable=True),
    Column("post_incident_notes", Text, nullable=True),
    Column("correlation_id", String(128), nullable=True, index=True),
    # Authoritative contract payload. Nullable so a row written by a narrower writer is still readable.
    Column("document", JSON, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(_sql_in("severity", SEVERITIES), name="severity"),
    CheckConstraint(_sql_in("status", INCIDENT_STATUSES), name="status"),
    CheckConstraint(_sql_in("service_environment", ENVIRONMENTS), name="environment"),
    Index("ix_incidents_service_opened", "service_name", "opened_at"),
)

evidence = Table(
    "evidence",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("evidence_id", String(128), nullable=False, unique=True, index=True),
    Column("kind", String(50), nullable=False),
    Column("collector", String(50), nullable=False),
    Column("collected_at", DateTime(timezone=True), nullable=False, index=True),
    Column("summary", String(280), nullable=False),
    Column("service_name", String(64), nullable=True, index=True),
    Column("service_environment", String(20), nullable=True),
    Column("service_namespace", String(64), nullable=True),
    Column("window_start", DateTime(timezone=True), nullable=True),
    Column("window_end", DateTime(timezone=True), nullable=True),
    Column("incident_id", String(128), nullable=True, index=True),
    Column("correlation_id", String(128), nullable=True, index=True),
    Column("document", JSON, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(_sql_in("kind", EVIDENCE_KINDS), name="kind"),
    Index("ix_evidence_service_collected", "service_name", "collected_at"),
)

remediation_proposals = Table(
    "remediation_proposals",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("proposal_id", String(128), nullable=False, unique=True, index=True),
    Column("incident_id", String(128), nullable=False, index=True),
    Column("category", String(64), nullable=False),
    Column("risk", String(20), nullable=False),
    Column("confidence", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("expires_at", DateTime(timezone=True), nullable=True, index=True),
    Column("document", JSON, nullable=True),
    ForeignKeyConstraint(
        ["incident_id"], ["incidents.incident_id"], name="incident", ondelete="CASCADE"
    ),
)

approvals = Table(
    "approvals",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("approval_id", String(128), nullable=False, unique=True, index=True),
    Column("proposal_id", String(128), nullable=False, index=True),
    Column("incident_id", String(128), nullable=False, index=True),
    Column("action_hash", String(80), nullable=False),
    Column("decision", String(20), nullable=False),
    Column("approver", String(254), nullable=False, index=True),
    Column("decided_at", DateTime(timezone=True), nullable=False, index=True),
    Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
    Column("consumed_at", DateTime(timezone=True), nullable=True),
    Column("document", JSON, nullable=True),
    CheckConstraint(_sql_in("decision", APPROVAL_DECISIONS), name="decision"),
    ForeignKeyConstraint(
        ["incident_id"], ["incidents.incident_id"], name="incident", ondelete="CASCADE"
    ),
)

audit_events = Table(
    "audit_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_id", String(128), nullable=False, unique=True, index=True),
    Column("occurred_at", DateTime(timezone=True), nullable=False, index=True),
    Column("actor_type", String(20), nullable=False),
    Column("actor_id", String(254), nullable=False, index=True),
    Column("event_type", String(40), nullable=False, index=True),
    Column("subject", String(128), nullable=False, index=True),
    Column("result", String(20), nullable=False),
    Column("correlation_id", String(128), nullable=False, index=True),
    Column("incident_id", String(128), nullable=True, index=True),
    Column("approval_id", String(128), nullable=True, index=True),
    Column("action_hash", String(80), nullable=True),
    Column("tool", String(128), nullable=True),
    # The authoritative contract payload. ``digest`` and ``previous_digest`` are columns rather than
    # payload fields because the chain is what an operator queries when verifying a history.
    Column("document", JSON, nullable=False),
    Column("previous_digest", String(80), nullable=True),
    Column("digest", String(80), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(_sql_in("actor_type", AUDIT_ACTOR_TYPES), name="actor_type"),
    CheckConstraint(_sql_in("result", AUDIT_RESULTS), name="result"),
    Index("ix_audit_events_subject_occurred", "subject", "occurred_at"),
)
