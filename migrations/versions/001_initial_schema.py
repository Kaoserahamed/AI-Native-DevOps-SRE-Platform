"""Initial database schema for incident tracking and agent execution.

Creates tables for:
- Incidents
- Evidence
- Remediation proposals and approvals
- Agent executions
- Audit log
- Idempotency keys
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
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
    UniqueConstraint,
    text,
)
from sqlalchemy.ext.asyncio import AsyncConnection

version = 1
description = "Initial schema: incidents, evidence, remediation, agent execution, audit"


async def up(conn: AsyncConnection, metadata: MetaData) -> None:
    """Apply migration."""
    # Incidents table
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
        Column("confidence", Integer, nullable=True),  # Stored as int 0-100
        Column("resolution_summary", Text, nullable=True),
        Column("post_incident_notes", Text, nullable=True),
        Column("correlation_id", String(128), nullable=True, index=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        CheckConstraint("severity IN ('sev1', 'sev2', 'sev3')", name="ck_incidents_severity"),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'investigating', 'mitigating', 'resolved', 'reopened', 'closed')",
            name="ck_incidents_status",
        ),
        CheckConstraint(
            "service_environment IN ('development', 'staging', 'production')",
            name="ck_incidents_environment",
        ),
    )

    # Evidence table
    evidence = Table(
        "evidence",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("evidence_id", String(128), nullable=False, unique=True, index=True),
        Column("kind", String(50), nullable=False),
        Column("collector", String(50), nullable=False),
        Column("collected_at", DateTime(timezone=True), nullable=False, index=True),
        Column("summary", String(280), nullable=False),
        Column("excerpt", Text, nullable=True),
        Column("payload", JSON, nullable=True),
        Column("size_bytes", Integer, nullable=False, default=0),
        Column("redacted", Boolean, nullable=False, default=True),
        Column("service_name", String(64), nullable=True, index=True),
        Column("service_environment", String(20), nullable=True),
        Column("window_start", DateTime(timezone=True), nullable=True),
        Column("window_end", DateTime(timezone=True), nullable=True),
        Column("incident_id", String(128), nullable=True, index=True),
        Column("correlation_id", String(128), nullable=True, index=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        CheckConstraint(
            "kind IN ('metric_series', 'log_excerpt', 'trace_summary', 'kubernetes_object', 'deployment_event', 'configuration_diff')",
            name="ck_evidence_kind",
        ),
        Index("ix_evidence_service_collected", "service_name", "collected_at"),
    )

    # Remediation proposals table
    remediation_proposals = Table(
        "remediation_proposals",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("proposal_id", String(128), nullable=False, unique=True, index=True),
        Column("incident_id", String(128), nullable=False, index=True),
        Column("created_at", DateTime(timezone=True), nullable=False, index=True),
        Column("proposed_by", String(254), nullable=False),  # PrincipalId
        Column("category", String(50), nullable=False),
        Column("title", String(280), nullable=False),
        Column("description", Text, nullable=False),
        Column("changes", JSON, nullable=False),
        Column("risk_level", String(20), nullable=False),
        Column("estimated_duration_minutes", Integer, nullable=True),
        Column("validation_results", JSON, nullable=True),
        Column("status", String(20), nullable=False, index=True),
        Column("approval_id", String(128), nullable=True, index=True),
        Column("rejection_reason", Text, nullable=True),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired', 'superseded')",
            name="ck_proposals_status",
        ),
        ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.incident_id"],
            name="fk_proposals_incident",
            ondelete="CASCADE",
        ),
    )

    # Approvals table
    approvals = Table(
        "approvals",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("approval_id", String(128), nullable=False, unique=True, index=True),
        Column("proposal_id", String(128), nullable=False, index=True),
        Column("approved_by", String(254), nullable=False),
        Column("approved_at", DateTime(timezone=True), nullable=False, index=True),
        Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
        Column("action_hash", String(71), nullable=False),  # sha256:64hex
        Column("justification", Text, nullable=True),
        Column("conditions", JSON, nullable=True),
        Column("revoked", Boolean, nullable=False, default=False),
        Column("revoked_at", DateTime(timezone=True), nullable=True),
        Column("revoked_by", String(254), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        ForeignKeyConstraint(
            ["proposal_id"],
            ["remediation_proposals.proposal_id"],
            name="fk_approvals_proposal",
            ondelete="CASCADE",
        ),
    )

    # Agent executions table
    agent_executions = Table(
        "agent_executions",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("execution_id", String(128), nullable=False, unique=True, index=True),
        Column("agent_name", String(64), nullable=False, index=True),
        Column("started_at", DateTime(timezone=True), nullable=False, index=True),
        Column("completed_at", DateTime(timezone=True), nullable=True),
        Column("status", String(20), nullable=False, index=True),
        Column("incident_id", String(128), nullable=True, index=True),
        Column("input_payload", JSON, nullable=True),
        Column("output_payload", JSON, nullable=True),
        Column("error_message", Text, nullable=True),
        Column("llm_requests", Integer, nullable=False, default=0),
        Column("total_prompt_tokens", Integer, nullable=False, default=0),
        Column("total_completion_tokens", Integer, nullable=False, default=0),
        Column("correlation_id", String(128), nullable=True, index=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        CheckConstraint(
            "status IN ('running', 'success', 'failure', 'timeout', 'cancelled')",
            name="ck_executions_status",
        ),
        Index("ix_executions_agent_started", "agent_name", "started_at"),
    )

    # Audit log table
    audit_log = Table(
        "audit_log",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("audit_id", String(128), nullable=False, unique=True, index=True),
        Column("timestamp", DateTime(timezone=True), nullable=False, index=True),
        Column("actor_type", String(20), nullable=False),
        Column("actor_id", String(254), nullable=False, index=True),
        Column("action", String(100), nullable=False, index=True),
        Column("resource_type", String(50), nullable=False),
        Column("resource_id", String(128), nullable=False, index=True),
        Column("outcome", String(20), nullable=False),
        Column("details", JSON, nullable=True),
        Column("ip_address", String(45), nullable=True),
        Column("user_agent", String(500), nullable=True),
        CheckConstraint(
            "actor_type IN ('human', 'agent', 'automation', 'system')",
            name="ck_audit_actor_type",
        ),
        CheckConstraint("outcome IN ('success', 'failure', 'denied')", name="ck_audit_outcome"),
        Index("ix_audit_timestamp_action", "timestamp", "action"),
    )

    # Idempotency keys table
    idempotency_keys = Table(
        "idempotency_keys",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("idempotency_key", String(128), nullable=False, unique=True, index=True),
        Column("resource_type", String(50), nullable=False),
        Column("resource_id", String(128), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
        Column("response_payload", JSON, nullable=True),
        UniqueConstraint("idempotency_key", "resource_type", name="uq_idempotency"),
        Index("ix_idempotency_expires", "expires_at"),
    )

    # Create all tables
    await conn.run_sync(incidents.create)
    await conn.run_sync(evidence.create)
    await conn.run_sync(remediation_proposals.create)
    await conn.run_sync(approvals.create)
    await conn.run_sync(agent_executions.create)
    await conn.run_sync(audit_log.create)
    await conn.run_sync(idempotency_keys.create)


async def down(conn: AsyncConnection, _metadata: MetaData) -> None:
    """Rollback migration."""
    # Drop tables in reverse order (respecting foreign keys)
    tables = [
        "idempotency_keys",
        "audit_log",
        "agent_executions",
        "approvals",
        "remediation_proposals",
        "evidence",
        "incidents",
    ]

    for table_name in tables:
        await conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
