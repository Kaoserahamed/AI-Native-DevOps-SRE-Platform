# AI-Native DevOps & SRE Platform

A production-oriented reference implementation of an **AI-native DevOps/SRE control loop**: a demo
workload is instrumented end to end (logs, metrics, traces), degradation is detected against learned
baselines, an evidence-bounded AI agent diagnoses the likely cause, remediation is proposed, gated by an
explicit policy engine plus human approval, and finally applied as an auditable GitHub pull request. An
LLM never mutates production directly.

The repository optimizes for **verifiable engineering quality** over size: committed lockfiles, CI gates
that run the same commands a developer can run locally, deterministic test fixtures, and an audit trail
for every agent decision.

## Control loop

```mermaid
flowchart LR
  A[GitHub] --> B[CI/CD]
  B --> C[Kubernetes]
  C --> D[Demo application]
  D --> E[OpenTelemetry]
  E --> F[Logs / Metrics / Traces]
  F --> G[Detection + AI incident agents]
  G --> H{Diagnose or insufficient evidence}
  H --> I[Remediation proposal]
  I --> J[Policy / risk engine]
  J --> K[Human approval]
  K --> L[GitHub issue + remediation PR]
  L --> B
```

## Delivery status

The platform is built incrementally. This table tracks the phases defined in
[`AI_Native_DevOps_SRE_DataFactor_Agentic_Task_List.md`](AI_Native_DevOps_SRE_DataFactor_Agentic_Task_List.md).

| Phase | Scope | Status |
| --- | --- | --- |
| 0 (Task 0.1) | Repository governance | Implemented |
| 0 (Tasks 0.2-0.3) | Tooling standards, reproducible dependencies | Implemented |
| 1 | Architecture, ADRs, versioned contracts | Implemented |
| 2 (Tasks 2.1-2.2) | Demo production application: FastAPI service, Next.js frontend | Implemented |
| 2 (Task 2.3) | Hardened application containers | Implemented |
| 3 | Kubernetes platform (base, dev/staging/prod overlays, hardening, manifest tests) | Implemented |
| 4 | Terraform infrastructure (reusable modules, environments, committed lockfile, config tests) | Implemented |
| 5-6 | OpenTelemetry SDK + collector, Prometheus scrape config, alert rules, starter dashboard | Partial — app metrics/tracing, collector, `prometheus.yml`, `alert-rules.yml`, `demo-api-overview.json` exist; `observability/grafana/` empty, no K8s-health/SLO/agent/cost dashboards |
| 7 | SLO definitions, incident persistence model, incident lifecycle API | Not implemented — contracts + state-machine validation only (`packages/contracts/incidents.py`); no SLO docs, no incident store/API service |
| 8 (Task 8.1) | Provider-agnostic LLM interface (budget/retry/fallback/structured output + tests) | Implemented (`packages/llm/`, `tests/llm/`) |
| 8-10 (Tasks 8.2-10.3) | Evidence retrieval, analysis/anomaly agents, remediation + approval runtime, GitHub automation, worker | Not implemented — `services/` has only `demo_api`; `packages/github_client`, `kubernetes_client`, `observability`, `policy` are empty `app/`+`tests/` scaffolds |
| 11-19 | Migrations, queue/worker, integration/e2e/chaos tiers, CI/CD gates, runbooks, DR | Partial — demo-app Postgres/Redis integration exists; `migrations/`, `compose*.yaml`, full CI workflows (only `repo-policy.yml` exists), `tests/integration|e2e|chaos` contents, `docs/20-runbooks/` contents missing |
| 20-26 | Remaining docs, threat model, performance, agent evaluation, e2e demo | Partial — `docs/00,01,03,04,08,18` + 10 ADRs exist; `docs/05-07,09-17,19`, threat model, and e2e demo missing |

## Quick start

Prerequisites (exact versions and pinning locations are documented in
[docs/03-local-development.md](docs/03-local-development.md)):

- Python 3.11 or newer
- Node.js 20.19 or newer (demo frontend and repository tooling)
- [`uv`](https://docs.astral.sh/uv/) for reproducible Python dependency resolution

```bash
git clone https://github.com/Kaoserahamed/AI-Native-DevOps-SRE-Platform.git
cd AI-Native-DevOps-SRE-Platform
python -m pip install uv
uv sync --frozen --all-extras
uv run pre-commit install
npm ci                 # repository tooling plus every npm workspace (the demo frontend)
```

Every gate CI runs on a pull request is available locally through one command:

```bash
make verify            # repository policy, format, lint, typecheck, fast tests, frontend tooling
make test-integration  # ephemeral PostgreSQL/Redis/OTel tiers
```

Windows has no `make` by default; [docs/03-local-development.md](docs/03-local-development.md) lists the
equivalent commands, including the Node tooling fallback for clone paths that contain `&`.

## Repository layout

```text
apps/demo-app/       Demo workload: Next.js frontend (npm workspace) and the workload README
services/            Platform services: api, incident-agent, anomaly-agent, remediation-agent, worker
packages/            Shared libraries: contracts, observability, github_client, kubernetes_client,
                     llm, policy, test_fixtures
infra/kubernetes/    Kustomize base, environment overlays, policies, manifest tests
infra/terraform/     Reusable modules, environment roots, IaC tests
observability/       OpenTelemetry collector, Prometheus rules, Grafana dashboards, alert definitions
docs/                Architecture, ADRs, runbooks, SLOs, threat model, governance
scripts/             Local + CI helper scripts (repository policy checks, load generation)
tests/               Cross-cutting contract, integration, e2e, chaos suites and fixtures
```

## Documentation

Repository-wide governance, architecture and development documents are available now; the remaining
documents are added by the phase that implements them and linked here once they exist
(`docs/05-api.md`, `docs/06-data-model.md`, `docs/07-observability.md`,
`docs/09-incident-lifecycle.md`, `docs/10-security.md`,
`docs/11-threat-model.md`, `docs/12-kubernetes.md`, `docs/13-terraform.md`, `docs/14-ci-cd.md`,
`docs/15-testing-strategy.md`, `docs/16-sre-slos.md`, `docs/17-cost-optimization.md`,
`docs/19-disaster-recovery.md`, `docs/20-runbooks/`).

| Document | Purpose |
| --- | --- |
| [docs/00-overview.md](docs/00-overview.md) | Purpose, principles, audience and glossary |
| [docs/01-architecture.md](docs/01-architecture.md) | Context, components, trust boundaries, failure domains |
| [docs/03-local-development.md](docs/03-local-development.md) | Supported runtimes, tooling pins, canonical commands |
| [docs/04-configuration.md](docs/04-configuration.md) | Every environment variable the platform reads |
| [docs/08-ai-agents.md](docs/08-ai-agents.md) | LLM interface, budgets, retry/fallback policy, agent verification |
| [apps/demo-app/README.md](apps/demo-app/README.md) | The demo workload: endpoints, panels, tests, configuration |
| [docs/18-governance.md](docs/18-governance.md) | Branch protection, review and change policy |
| [docs/adr/](docs/adr/README.md) | Architecture decision records |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to propose and validate changes |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting and security expectations |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community expectations and enforcement |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

## Security and agent safety model

- Telemetry, logs and GitHub content are treated as **untrusted input**; they are never allowed to
  redefine agent policy.
- Agent tools are allowlisted, read-only by default, and fully audited.
- Production mutation requires a policy pass **and** an explicit, expiring human approval; approvals are
  bound to an action hash so a replayed approval cannot authorize a changed action.
- Secrets, Terraform state, kubeconfigs and `.env` files are never committed; CI enforces this.

See `docs/10-security.md` and `docs/11-threat-model.md` for the full model once those documents land.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
