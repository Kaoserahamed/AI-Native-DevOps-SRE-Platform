# Architecture decision records

ADRs capture decisions that are expensive to reverse or that shape trust boundaries, the data model, the
agent safety model or day-to-day operability. Each record states its context, the decision, the
alternatives that were rejected, the consequences and how the decision is validated.

Use the template [0000-template.md](0000-template.md) for new records and the
["Architecture decision" issue template](../../.github/ISSUE_TEMPLATE/architecture_decision.yml) to
propose one.

Rules:

- ADRs are **immutable** once accepted. A later decision is a new ADR that states
  `Superseded by ADR-NNNN` in its predecessor and `Supersedes ADR-NNNN` in itself.
- Numbering is sequential and never reused.
- An ADR that changes a trust boundary, credentials or the approval model requires security review and a
  threat-model update in the same pull request.
- ADRs are written in the same pull request as the change they justify, or before it.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-kubernetes-deployment-model.md) | Kubernetes deployment model: Kustomize base with environment overlays | Accepted |
| [0002](0002-opentelemetry-architecture.md) | OpenTelemetry as the single telemetry pipeline (SDK → collector → backends) | Accepted |
| [0003](0003-prometheus-grafana.md) | Prometheus for metrics and alerting, Grafana for visualization | Accepted |
| [0004](0004-postgresql-storage.md) | PostgreSQL as the transactional system of record | Accepted |
| [0005](0005-redis-queue-and-cache.md) | Redis for the job queue, short-lived cache and rate limiting | Accepted |
| [0006](0006-llm-provider-abstraction.md) | Provider-agnostic LLM interface with budgets and structured output | Accepted |
| [0007](0007-human-approval-model.md) | Human approval bound to an action hash for every production change | Accepted |
| [0008](0008-github-integration.md) | GitHub as the system of record for change, via a least-privilege adapter | Accepted |
| [0009](0009-terraform-environment-separation.md) | Terraform with reusable modules and per-environment state separation | Accepted |
