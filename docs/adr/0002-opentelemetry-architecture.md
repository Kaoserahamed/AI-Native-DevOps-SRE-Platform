# ADR-0002: One OpenTelemetry pipeline from SDK to backends

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** Platform maintainer
- **Related:** `docs/07-observability.md`, `observability/otel/`, phase 5 of the implementation backlog

## Context

Incident detection and diagnosis are only as good as the telemetry behind them. The platform needs
correlated traces, metrics and logs across the demo backend, the frontend, the platform API, the workers
and the agents, with consistent service identity, propagation across HTTP and queue boundaries, and the
ability to bound what reaches the AI agents (both for cost and for prompt-injection safety).

## Decision

We will instrument every service with the OpenTelemetry SDK, export over OTLP to a single Collector
deployment, and let the Collector own sampling, resource enrichment, redaction and fan-out to Prometheus,
the log store and the trace backend. Services use `packages/observability` for a shared bootstrap so
resource attributes (`service.name`, `service.version`, `deployment.environment`), propagators and the
log/trace correlation IDs are identical everywhere. Trace context propagates through HTTP (W3C
`traceparent`) and through queue jobs (explicit carrier stored with the job). Sampling strategy is
documented in `observability/otel/README.md` and starts with deterministic head sampling for errors plus
tail sampling for slow traces.

## Alternatives considered

| Alternative | Why it was rejected |
| --- | --- |
| Direct SDK export to each backend | Sampling and redaction logic would be duplicated per service, and a backend change would require redeploying applications |
| Vendor-specific agents | Lock-in, and the reference implementation should show portable instrumentation |
| Scraping-only metrics without a collector | No trace processing, no redaction layer, and metrics cardinality would be uncontrolled at the source |
| Auto-instrumentation only | Insufficient correlation across queue boundaries and no domain-specific spans for incident evidence |

## Consequences

- **Positive:** one place to add redaction, sampling and cardinality control; backends are replaceable;
  correlation IDs work across HTTP, queue and database boundaries.
- **Negative:** the Collector is a critical dependency of observability, so it needs redundancy and its own
  health metrics; instrumentation adds latency overhead that must stay within budget.
- **Neutral:** instrumentation smoke tests become part of the contract test tier.

## Security, privacy and agent impact

TB-2 (telemetry → control plane) is the relevant boundary. The Collector is the enforcement point for
redaction: no secrets or credentials may reach the pipeline, and the evidence retrieval layer applies
additional per-query limits (time window, result count, payload size). Telemetry content is never treated
as instructions by the agents, and low-trust fields are not interpolated into prompt system sections.

## Validation

- Instrumentation smoke tests assert that a request produces a trace with expected spans, a metric series
  and a structured log line carrying the same `trace_id`.
- Propagation tests assert the trace context survives HTTP, database and queue boundaries.
- Collector configuration is validated in CI, and the e2e job asserts that telemetry from the demo
  deployment reaches the backends.
