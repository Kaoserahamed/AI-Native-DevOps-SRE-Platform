# ADR-0004: PostgreSQL is the transactional system of record

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** Platform maintainer
- **Related:** `docs/06-data-model.md`, `migrations/`, phase 13 of the implementation backlog

## Context

The platform stores incidents, evidence references, proposals, approvals, agent executions and audit
events. These records must be transactionally consistent (an approval must never be recorded without its
action hash, an incident transition must never skip a state), queryable by operators and reviewers, and
durable enough to reconstruct what an agent decided and why. Audit events are append-only by policy.

## Decision

We will use PostgreSQL as the single transactional store, accessed with SQLAlchemy 2.0 through
repository interfaces so SQL never leaks into business logic. Schema changes ship as **versioned
migrations** in `migrations/` (Alembic), with foreign keys, constraints, indexes and a dedicated audit
table. Mutating endpoints accept an idempotency key so a retried request cannot create duplicate
incidents, jobs or approvals. Real PostgreSQL runs in a dedicated integration test tier; unit and contract
tests use repository fakes.

## Alternatives considered

| Alternative | Why it was rejected |
| --- | --- |
| Document database (MongoDB) | The incident lifecycle is relational (incident → evidence → proposal → approval → audit) and benefits from constraints and transactions |
| SQLite | Not representative of production concurrency, replication and backup behaviour |
| Managed cloud database only | Prevents running the full loop locally and in CI |
| Event-sourcing-first design | Interesting but adds projection complexity the reference implementation does not need; audit tables already give an append-only trail |
| Folding audit into application logs | Logs are not a reliable system of record and are not queryable transactionally |

## Consequences

- **Positive:** strong consistency for the approval and lifecycle state machines, mature tooling
  (migrations, backups, point-in-time recovery), and one place to enforce audit immutability.
- **Negative:** an operational dependency with connection pooling, retention and backup obligations; the
  database becomes a single point of failure unless the DR procedure is followed.
- **Neutral:** migration-up and migration-down paths are tested where the database supports them, and
  schema integrity tests run in CI.

## Security, privacy and agent impact

TB-7 (platform → databases) applies: per-service credentials with least privilege, no shared superuser,
migrations reviewed by a code owner. Evidence payloads are stored as bounded, sanitized excerpts with
references rather than raw telemetry, so no credentials or user data accumulate in the database. Audit
rows are append-only: the application role has no `UPDATE`/`DELETE` grant on the audit table.

## Validation

- Migration tests run up/down against an ephemeral PostgreSQL in CI; schema integrity tests assert
  constraints and indexes exist.
- Repository contract tests run against both the fake and real implementations to prove behaviour
  parity.
- The DR documentation includes a restore drill that restores a backup into a non-production database.
