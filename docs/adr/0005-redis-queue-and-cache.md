# ADR-0005: Redis Streams for the job queue, plus cache and rate limiting

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** Platform maintainer
- **Related:** `docs/06-data-model.md`, `docs/08-ai-agents.md`, phase 14 of the implementation backlog

## Context

Agent work is slow, bursty and failure-prone: evidence retrieval, LLM calls and GitHub writes can each
take seconds to minutes and can fail independently. Detection must not block the API, retries must not
duplicate side effects, and operators need to see what is pending, in flight or dead-lettered. The
platform also needs short-lived caching for reference data and counters for rate limiting agent actions.

## Decision

We will use Redis Streams with consumer groups as the job queue: jobs carry a correlation ID, a retry
count and an idempotency key; pending entries provide the visibility timeout; a claim operation recovers
jobs from crashed workers; and exhausted retries move to a dead-letter stream with the failure reason.
The same Redis instance provides a bounded cache for read-mostly reference data and the counters that back
the policy engine's rate limits. Queue loss is treated as recoverable: pending work is re-derived from
incident state in PostgreSQL, which is why the database, not the queue, is the system of record.

## Alternatives considered

| Alternative | Why it was rejected |
| --- | --- |
| Celery with Redis broker | Hides retry/visibility semantics behind a framework, making dead-letter inspection and the audit story weaker; the workload is small enough to manage explicitly |
| RabbitMQ | A second stateful system to operate for no functional gain at this scale |
| Kafka | Excellent throughput and replay, but operationally heavy for a reference implementation and unnecessary for incident volumes |
| PostgreSQL as the queue (`FOR UPDATE SKIP LOCKED`) | Reasonable, but it couples agent throughput to the transactional database and loses Redis's cheap counters and TTL caching |
| Cloud queue (SQS/Pub/Sub) | Prevents a fully local and CI-runnable loop |

## Consequences

- **Positive:** one dependency covers queueing, caching and rate limiting; pending and dead-letter state is
  directly observable; retries, backoff and idempotency are explicit and testable.
- **Negative:** at-least-once delivery means every consumer must be idempotent; Redis needs memory sizing,
  persistence decisions and a documented recovery expectation (queue contents are not authoritative).
- **Neutral:** the worker owns the backoff policy, so it is unit-testable without Redis.

## Security, privacy and agent impact

Redis holds no long-term sensitive data: cache entries have TTLs and job payloads carry evidence IDs
rather than evidence bodies, so telemetry text (untrusted input, TB-2) does not accumulate in the queue.
Redis is reachable only from the control plane, uses authentication with per-service credentials, and the
rate-limit counters it holds are the enforcement point for agent action budgets.

## Validation

- Queue contract tests (against a fake) and worker integration tests (against ephemeral Redis) cover
  retry, backoff, visibility timeout, claim-after-crash and dead-letter paths.
- A chaos scenario removes Redis and asserts the documented behaviour: the API keeps serving reads, the
  queue stops, and pending work is recovered once Redis returns.
