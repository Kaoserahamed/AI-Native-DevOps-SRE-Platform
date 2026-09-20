# ADR-0003: Prometheus for metrics and alerting, Grafana for visualization

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** Platform maintainer
- **Related:** `docs/07-observability.md`, `docs/16-sre-slos.md`, `observability/prometheus/`,
  `observability/grafana/`, phase 6 of the implementation backlog

## Context

The platform must detect degradation reliably enough that an AI agent can be asked to diagnose it. That
requires metric collection with server-side recording rules, alert rules expressed as code, SLO
burn-rate evaluation, and dashboards that humans and agents can both reason about. Alerts are the entry
point of the incident lifecycle, so their definition, review and testing matter as much as the
application code.

## Decision

We will use Prometheus as the metrics store and rule evaluator, Alertmanager for routing, and Grafana for
dashboards. Rule files (recording, alerting, SLO burn-rate) live in `observability/prometheus/` and are
unit-tested with `promtool test rules`. Dashboards live as JSON in `observability/grafana/` and are
provisioned from git. Platform and application metrics follow the naming and label conventions documented
in `docs/07-observability.md`, and every alert ships with a runbook link and a severity.

## Alternatives considered

| Alternative | Why it was rejected |
| --- | --- |
| Managed SaaS observability | Cost and lock-in; the reference implementation should be runnable locally and in CI |
| VictoriaMetrics or Thanos | Valuable at scale, but the demo's scale does not justify the extra operational surface |
| Grafana Mimir | Same reasoning; also adds a distributed-systems dependency to a reference project |
| Grafana Alerting instead of Prometheus rules | Splits the alert definitions away from the query language and the CI validation story (`promtool`) |

## Consequences

- **Positive:** alert and recording rules are code, reviewable, versioned and unit-testable; dashboards are
  reproducible; the same rules power SLO burn-rate alerts that feed the incident lifecycle.
- **Negative:** Prometheus needs storage sizing and retention decisions; high-cardinality labels can blow
  up memory and must be policed in code review and by metric naming rules.
- **Neutral:** dashboards are exported JSON, so a UI-only change must be re-exported to git; the trade-off
  is that dashboards are reviewable and restorable.

## Security, privacy and agent impact

No new trust boundary. Metrics are treated as untrusted data (TB-2) and must never contain secrets,
tokens, user identifiers or request bodies. Label values that carry user-supplied data are prohibited by
the naming convention, which also protects the AI evidence path from prompt injection through metric
labels.

## Validation

- `promtool check rules` and `promtool test rules` run in CI over every rule file.
- Alert rules are exercised by the chaos tier: a controlled fault must produce the expected alert,
  including a documented expected-behaviour statement.
- The e2e job asserts that the demonstration scenario triggers the intended alert and creates an incident.
