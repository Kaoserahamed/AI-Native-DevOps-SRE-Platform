# AI-Native DevOps & SRE Platform — Agentic Implementation Backlog

## 0. Goal

Build a production-oriented repository that demonstrates an AI-native DevOps/SRE control loop:

GitHub → CI/CD → Kubernetes → Application → OpenTelemetry → Logs/Metrics/Traces → AI Incident Agent → Detect → Diagnose → Suggest Fix → Create PR → Human Approval → Controlled Remediation

Primary goal: maximize real engineering quality and verifiability rather than repository size.

The implementation should be deliberately incremental. Every feature is paired with tests, documentation, security checks, and CI evidence.

> **Important:** Never manufacture, backdate, or artificially fragment Git history. Commits must represent real logical changes completed during the project.

---

# 1. Agent Operating Rules

Use these rules for every coding agent working on the repository.

- Start each task by reading the current README, architecture docs, relevant code, tests, and CI workflows.
- Create or update one GitHub Issue for each meaningful task.
- Keep commits narrowly scoped: one architectural change, feature, refactor, test improvement, documentation change, or security improvement per commit.
- Every production-code commit should add or update tests unless the change is genuinely non-testable; document the reason.
- Every externally observable behavior change must update API/OpenAPI docs or user/operator documentation.
- Run the repository's canonical verification commands through CI. Local execution is optional, not required.
- Never commit secrets, cloud credentials, generated state, `.env` files, Terraform state, kubeconfigs, or production data.
- Prefer interfaces and adapters around external systems such as GitHub, Kubernetes, Prometheus, PostgreSQL, Redis, and LLM providers.
- Use deterministic fixtures and fake adapters for unit/contract tests.
- Use real services only in dedicated integration/e2e jobs.
- Do not allow an LLM to directly execute arbitrary production changes.
- All production-changing actions require explicit human approval.
- Every agent action must be auditable: who/what agent, input evidence, decision, confidence, action, result.
- Keep large modules decomposed. Target small cohesive files and avoid god files.
- Update diagrams, runbooks, configuration reference, and changelog as architecture evolves.
- Never silently weaken tests or CI gates to make a build pass.

---

# 2. Definition of Done

A task is complete only when all applicable conditions are true:

1. Code implemented.
2. Unit tests added/updated.
3. Integration/contract/e2e test added where applicable.
4. Security implications reviewed.
5. Observability added for important paths.
6. Configuration documented.
7. README/docs updated.
8. CI validates the change.
9. Migration/rollback impact considered.
10. No secrets or generated infrastructure state committed.
11. Commit message explains the real logical change.
12. GitHub Issue/PR acceptance criteria are satisfied.

---

# 3. Target Repository Structure

```text
ai-native-devops-sre/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── security.yml
│   │   ├── container.yml
│   │   ├── terraform.yml
│   │   ├── k8s.yml
│   │   ├── e2e.yml
│   │   ├── release.yml
│   │   └── dependency-review.yml
│   ├── dependabot.yml
│   ├── CODEOWNERS
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
│
├── apps/
│   └── demo-app/
│       ├── backend/
│       ├── frontend/
│       ├── tests/
│       └── README.md
│
├── services/
│   ├── api/
│   │   ├── app/
│   │   └── tests/
│   ├── incident-agent/
│   │   ├── app/
│   │   └── tests/
│   ├── anomaly-agent/
│   │   ├── app/
│   │   └── tests/
│   ├── remediation-agent/
│   │   ├── app/
│   │   └── tests/
│   └── worker/
│       ├── app/
│       └── tests/
│
├── packages/
│   ├── contracts/
│   ├── observability/
│   ├── github_client/
│   ├── kubernetes_client/
│   ├── llm/
│   ├── policy/
│   └── test_fixtures/
│
├── infra/
│   ├── terraform/
│   │   ├── modules/
│   │   ├── environments/
│   │   └── tests/
│   └── kubernetes/
│       ├── base/
│       ├── overlays/
│       ├── policies/
│       └── tests/
│
├── observability/
│   ├── otel/
│   ├── prometheus/
│   ├── grafana/
│   ├── alerts/
│   └── dashboards/
│
├── migrations/
│
├── tests/
│   ├── contract/
│   ├── integration/
│   ├── e2e/
│   ├── chaos/
│   └── fixtures/
│
├── docs/
│   ├── 00-overview.md
│   ├── 01-architecture.md
│   ├── 02-repository-structure.md
│   ├── 03-local-development.md
│   ├── 04-configuration.md
│   ├── 05-api.md
│   ├── 06-data-model.md
│   ├── 07-observability.md
│   ├── 08-ai-agents.md
│   ├── 09-incident-lifecycle.md
│   ├── 10-security.md
│   ├── 11-threat-model.md
│   ├── 12-kubernetes.md
│   ├── 13-terraform.md
│   ├── 14-ci-cd.md
│   ├── 15-testing-strategy.md
│   ├── 16-sre-slos.md
│   ├── 17-cost-optimization.md
│   ├── 18-governance.md
│   ├── 19-disaster-recovery.md
│   ├── 20-runbooks/
│   ├── adr/
│   └── diagrams/
│
├── scripts/
├── Makefile
├── compose.yaml
├── compose.test.yaml
├── Dockerfile
├── pyproject.toml
├── uv.lock
├── package.json
├── package-lock.json
├── go.mod
├── go.sum
├── .env.example
├── SECURITY.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md
└── README.md
```

---

# 4. Phase 0 — Repository Foundation

## Task 0.1 — Bootstrap repository governance
- [x] Initialize repository.
- [x] Add README skeleton.
- [x] Add LICENSE appropriate for the project.
- [x] Add CONTRIBUTING.md.
- [x] Add CODE_OF_CONDUCT.md.
- [x] Add SECURITY.md.
- [x] Add CHANGELOG.md.
- [x] Add CODEOWNERS.
- [x] Add PR template.
- [x] Add issue templates for feature, bug, incident, security, architecture decision.
- [x] Define branch protection recommendations in docs.

**Tests/CI:** markdown link check and repository policy validation.

**Commit:** `chore: establish repository governance`

## Task 0.2 — Define coding/tooling standards
- [x] Python lint/format/type-check configuration.
- [x] TypeScript lint/format/type-check configuration.
- [x] Go formatting/lint configuration.
- [x] EditorConfig.
- [x] Pre-commit configuration where appropriate.
- [x] Pin action versions by commit SHA where practical.
- [x] Document supported runtime versions.

**Commit:** `chore: define language and tooling standards`

## Task 0.3 — Reproducible dependency management
- [x] Pin Python dependencies.
- [x] Commit `uv.lock` or chosen Python lockfile.
- [x] Commit npm lockfile.
- [x] Commit Go module metadata. — Not applicable: the platform is Python and TypeScript, so no Go module
      exists and `go.mod`/`go.sum` are intentionally absent. The Go lint policy is defined in
      `.golangci.yml` and a Go component must commit module metadata with its first package
      (see `docs/03-local-development.md`, "Go components").
- [x] Establish dependency update policy.
- [x] Add Dependabot/Renovate.
- [x] Document upgrade procedure.

**Acceptance:** fresh CI runner reproduces dependency resolution deterministically.

**Commit:** `chore: make dependency resolution reproducible`

---

# 5. Phase 1 — Architecture and Contracts

## Task 1.1 — Architecture specification
- [x] Write system context diagram.
- [x] Write container/component diagram.
- [x] Document control-plane vs data-plane responsibilities.
- [x] Document trust boundaries.
- [x] Document sync vs async interactions.
- [x] Document failure domains.

**Commit:** `docs: define platform architecture`

## Task 1.2 — ADR framework
Create ADRs for:
- [x] Kubernetes deployment model.
- [x] OpenTelemetry architecture.
- [x] Prometheus/Grafana choice.
- [x] PostgreSQL data storage.
- [x] Redis queue/cache usage.
- [x] LLM provider abstraction.
- [x] Human approval model.
- [x] GitHub integration.
- [x] Terraform environment separation.

**Commit:** `docs: add architecture decision records`

## Task 1.3 — Shared contracts
- [x] Incident schema.
- [x] Alert schema.
- [x] Evidence schema.
- [x] Agent decision schema.
- [x] Remediation proposal schema.
- [x] Approval schema.
- [x] Audit event schema.
- [x] API error schema.

Use versioned schemas.

**Tests:** schema validation tests and backward-compatibility tests.

**Commit:** `feat: add versioned platform contracts`

---

# 6. Phase 2 — Demo Production Application

The repository needs a realistic target workload so the platform can produce and investigate real telemetry.

## Task 2.1 — FastAPI demo backend
- [x] Health endpoint.
- [x] Readiness endpoint.
- [x] Metrics endpoint.
- [x] Structured logging.
- [x] Request correlation ID.
- [x] PostgreSQL integration.
- [x] Redis integration.
- [x] One intentionally controllable failure mode behind a test-only flag.
- [x] Graceful shutdown.
- [x] Configuration validation.

**Tests:** unit + API contract + database integration.

**Commit:** `feat: add observable FastAPI demo service`

## Task 2.2 — Next.js demo frontend
- [x] Typed API client.
- [x] Loading/error states.
- [x] Health/status view.
- [x] Request correlation display where useful.
- [ ] Production Docker build.
- [x] Basic component tests.
- [x] E2E smoke tests. — `tests/e2e/smoke.mjs` builds the standalone output and drives the production
      entrypoint against a stub backend (page, static assets, `/api` proxy, correlation headers). The
      browser-driven end-to-end tier that exercises a deployed revision belongs to Phase 15.4/16.6.

**Commit:** `feat: add demo web frontend`

## Task 2.3 — Containerization
- [ ] Multi-stage backend image.
- [ ] Multi-stage frontend image.
- [ ] Non-root user.
- [ ] Read-only filesystem compatibility where practical.
- [ ] Healthcheck.
- [ ] Minimal base images.
- [ ] Image metadata labels.
- [ ] SBOM generation plan.

**Security:** Trivy/Grype scan.

**Commit:** `build: harden application containers`

---

# 7. Phase 3 — Kubernetes Platform

## Task 3.1 — Kubernetes base manifests
- [ ] Namespace.
- [ ] ConfigMap.
- [ ] Secret references only; never hardcode secrets.
- [ ] Deployment.
- [ ] Service.
- [ ] Ingress/Gateway as selected.
- [ ] ServiceAccount.
- [ ] RBAC.
- [ ] PodDisruptionBudget.
- [ ] HPA.
- [ ] NetworkPolicy.
- [ ] Resource requests/limits.

**Validation:** kubeconform + kube-linter.

**Commit:** `feat: deploy demo application to Kubernetes`

## Task 3.2 — Environment overlays
- [ ] Base configuration.
- [ ] Development overlay.
- [ ] Staging overlay.
- [ ] Production overlay.
- [ ] Environment-specific resource sizing.
- [ ] Environment-specific observability configuration.
- [ ] Environment-specific policy settings.

**Commit:** `feat: add Kubernetes environment overlays`

## Task 3.3 — Kubernetes security controls
- [ ] Pod Security Standards.
- [ ] SecurityContext.
- [ ] Least-privilege ServiceAccounts.
- [ ] RBAC minimization.
- [ ] Network segmentation.
- [ ] Admission/policy checks.
- [ ] Secret handling documentation.

**Commit:** `security: enforce Kubernetes workload hardening`

---

# 8. Phase 4 — Terraform Infrastructure

## Task 4.1 — Terraform foundation
- [ ] Provider configuration.
- [ ] Backend/state strategy.
- [ ] Environment separation.
- [ ] Variables/outputs.
- [ ] Naming conventions.
- [ ] Tags/labels.
- [ ] Provider version constraints.

**Commit:** `feat: establish Terraform infrastructure structure`

## Task 4.2 — Reusable modules
Create focused modules for:
- [ ] Kubernetes cluster.
- [ ] PostgreSQL.
- [ ] Redis.
- [ ] Container registry.
- [ ] Networking where applicable.
- [ ] Monitoring dependencies where applicable.

- [ ] Version module interfaces.
- [ ] Document module inputs/outputs.

**Commit:** `refactor: introduce reusable Terraform modules`

## Task 4.3 — Lock and policy discipline
- [ ] Generate and commit `.terraform.lock.hcl`.
- [ ] Pin providers/modules to explicit versions.
- [ ] Add fmt check.
- [ ] Add init without backend for static validation.
- [ ] Add validate.
- [ ] Add Trivy config/IaC scan.
- [ ] Add provider lock drift detection.

**Commit:** `chore: pin Terraform providers and enforce IaC reproducibility`

---

# 9. Phase 5 — OpenTelemetry

## Task 5.1 — Standard telemetry
- [ ] OpenTelemetry SDK initialization.
- [ ] HTTP traces.
- [ ] Database traces.
- [ ] Redis traces.
- [ ] Structured logs.
- [ ] Metrics.
- [ ] Trace/request correlation.
- [ ] Consistent resource/service attributes.

**Tests:** instrumentation smoke tests and propagation tests.

**Commit:** `feat: instrument services with OpenTelemetry`

## Task 5.2 — Collector
- [ ] Deploy OpenTelemetry Collector.
- [ ] Configure receivers.
- [ ] Configure processors.
- [ ] Configure exporters.
- [ ] Add batching and memory protection.
- [ ] Document sampling strategy.

**Commit:** `feat: add OpenTelemetry collector pipeline`

---

# 10. Phase 6 — Prometheus, Grafana and SRE Signals

## Task 6.1 — Metrics model
Create metrics for:
- [ ] request count.
- [ ] request latency.
- [ ] 4xx/5xx rate.
- [ ] dependency failures.
- [ ] queue depth.
- [ ] worker processing time.
- [ ] agent execution count.
- [ ] agent execution latency.
- [ ] agent error rate.
- [ ] PR creation outcomes.
- [ ] remediation approval outcomes.

**Commit:** `feat: define platform and application metrics`

## Task 6.2 — Grafana dashboards
- [ ] Application overview.
- [ ] Kubernetes health.
- [ ] SRE/SLO dashboard.
- [ ] AI agent operations dashboard.
- [ ] Cost/usage dashboard.
- [ ] Incident overview.

**Commit:** `feat: add operational Grafana dashboards`

## Task 6.3 — Alert rules
- [ ] High error rate.
- [ ] High latency.
- [ ] Pod restart spikes.
- [ ] OOM kills.
- [ ] CrashLoopBackOff.
- [ ] Deployment rollout failure.
- [ ] Database saturation.
- [ ] Redis saturation.
- [ ] SLO burn-rate alerts.

**Commit:** `feat: add SRE alert rules`

---

# 11. Phase 7 — SLO/SLA and Incident Model

## Task 7.1 — SLO definitions
Define measurable examples:
- [ ] availability SLO.
- [ ] API latency SLO.
- [ ] successful request SLO.
- [ ] incident acknowledgement target.
- [ ] detection target.
- [ ] recovery target.

Document:
- [ ] SLI.
- [ ] SLO.
- [ ] error budget.
- [ ] burn rate.

**Commit:** `feat: define service level objectives`

## Task 7.2 — Incident data model
Store:
- [ ] incident ID.
- [ ] severity.
- [ ] service.
- [ ] timestamps.
- [ ] triggering alerts.
- [ ] telemetry evidence references.
- [ ] suspected causes.
- [ ] confidence.
- [ ] proposed actions.
- [ ] approval events.
- [ ] resolution.
- [ ] post-incident notes.

**Commit:** `feat: add incident persistence model`

## Task 7.3 — Incident lifecycle API
- [ ] open.
- [ ] acknowledge.
- [ ] investigate.
- [ ] mitigate.
- [ ] resolve.
- [ ] reopen.
- [ ] close.

**Tests:** state-machine and invalid-transition tests.

**Commit:** `feat: implement incident lifecycle API`

---

# 12. Phase 8 — AI Agent Runtime

## Task 8.1 — LLM abstraction
- [ ] Provider interface.
- [ ] Timeout handling.
- [ ] Retry policy.
- [ ] Rate-limit handling.
- [ ] Token/cost accounting.
- [ ] Structured output.
- [ ] Model configuration.
- [ ] Provider fallback policy.

**Commit:** `feat: add provider-agnostic LLM interface`

## Task 8.2 — Evidence retrieval layer
The agent must retrieve bounded evidence rather than ingesting unlimited telemetry.

- [ ] Log query adapter.
- [ ] Prometheus query adapter.
- [ ] Kubernetes inspection adapter.
- [ ] Trace query adapter.
- [ ] GitHub deployment history adapter.
- [ ] Recent configuration/deployment diff retrieval.
- [ ] Evidence time-window constraints.
- [ ] Evidence size limits.

**Commit:** `feat: add bounded incident evidence retrieval`

## Task 8.3 — Incident analysis agent
Pipeline:

```text
Alert
  ↓
Normalize
  ↓
Collect evidence
  ↓
Correlate signals
  ↓
LLM analysis
  ↓
Structured diagnosis
  ↓
Confidence + uncertainty
  ↓
Recommended action
```

- [ ] Prompt templates versioned in repository.
- [ ] System instructions.
- [ ] Structured output schema.
- [ ] Evidence citations.
- [ ] Confidence field.
- [ ] "insufficient evidence" outcome.
- [ ] No-action outcome.
- [ ] Analysis timeout.

**Tests:** deterministic fixture-based agent tests.

**Commit:** `feat: implement incident analysis agent`

## Task 8.4 — Anomaly detection
Start with deterministic methods before introducing ML.

- [ ] Rolling baseline.
- [ ] Threshold deviations.
- [ ] Rate-of-change.
- [ ] Simple statistical anomaly detection.
- [ ] Alert deduplication.
- [ ] Correlation windows.
- [ ] False-positive suppression.

**Commit:** `feat: add telemetry anomaly detection`

## Task 8.5 — Root-cause correlation
Correlate:
- [ ] deployment events.
- [ ] pod restarts.
- [ ] application errors.
- [ ] latency changes.
- [ ] database errors.
- [ ] Redis errors.
- [ ] infrastructure events.

Output:
- [ ] suspected cause list.
- [ ] evidence for each cause.
- [ ] confidence.
- [ ] unresolved uncertainty.

**Commit:** `feat: add evidence-based root cause analysis`

---

# 13. Phase 9 — Remediation and Human Approval

## Task 9.1 — Remediation proposal engine
Allowed proposal categories:
- [ ] restart/rollout.
- [ ] rollback.
- [ ] configuration change.
- [ ] resource adjustment.
- [ ] code fix.
- [ ] alert tuning.
- [ ] cost optimization.

Every proposal must include:
- [ ] rationale.
- [ ] evidence.
- [ ] expected impact.
- [ ] blast radius.
- [ ] rollback plan.
- [ ] confidence.
- [ ] required permissions.

**Commit:** `feat: generate governed remediation proposals`

## Task 9.2 — Risk/policy engine
Implement explicit policy checks:
- [ ] no direct production mutation.
- [ ] production rollback requires approval.
- [ ] high-risk actions require additional approval.
- [ ] blocked namespaces/resources.
- [ ] maximum automated scope.
- [ ] rate limits.
- [ ] maintenance-window restrictions if configured.
- [ ] deny-by-default action policy.

**Commit:** `security: add remediation policy engine`

## Task 9.3 — Human approval workflow
- [ ] Approval endpoint/UI.
- [ ] Expiring approval.
- [ ] Approver identity.
- [ ] Approval comment.
- [ ] Action hash/idempotency key.
- [ ] Reject path.
- [ ] Timeout path.
- [ ] Reapproval when evidence changes materially.

**Commit:** `feat: require human approval for production actions`

---

# 14. Phase 10 — GitHub Integration and PR Automation

## Task 10.1 — GitHub adapter
- [ ] GitHub App/token abstraction.
- [ ] Repository metadata.
- [ ] Commit history retrieval.
- [ ] Deployment history retrieval.
- [ ] Issue creation.
- [ ] PR creation.
- [ ] PR comment/update.
- [ ] Checks/status retrieval.

**Security:** least-privilege permission matrix.

**Commit:** `feat: add GitHub integration adapter`

## Task 10.2 — Automatic incident issue
Generate issue containing:
- [ ] incident summary.
- [ ] severity.
- [ ] timeline.
- [ ] affected service.
- [ ] relevant metrics.
- [ ] log evidence.
- [ ] traces.
- [ ] recent deployments.
- [ ] suspected root cause.
- [ ] remediation proposal.

**Commit:** `feat: create evidence-backed GitHub incident issues`

## Task 10.3 — Automated fix PR
- [ ] Generate patch only from approved proposal.
- [ ] Create branch.
- [ ] Commit changes.
- [ ] Open PR.
- [ ] Add machine-readable PR metadata.
- [ ] Add incident reference.
- [ ] Add validation results.
- [ ] Never auto-merge production-changing PRs.

**Tests:** GitHub API mocked contract tests + sandbox integration tests.

**Commit:** `feat: open governed remediation pull requests`

---

# 15. Phase 11 — Cost Optimization Agent

## Task 11.1 — Cost evidence model
- [ ] Resource utilization.
- [ ] Requested vs actual CPU/memory.
- [ ] Replica utilization.
- [ ] Idle resources.
- [ ] Storage usage.
- [ ] LLM token usage.
- [ ] CI minutes.
- [ ] Registry/storage footprint.

**Commit:** `feat: collect cost optimization evidence`

## Task 11.2 — Cost recommendations
Produce non-mutating recommendations:
- [ ] rightsizing.
- [ ] autoscaling changes.
- [ ] idle resource cleanup.
- [ ] log retention adjustments.
- [ ] model selection/cost trade-offs.

Every recommendation must include assumptions and estimated impact.

**Commit:** `feat: add cost optimization recommendations`

---

# 16. Phase 12 — Agent Safety, Governance and Auditability

## Task 12.1 — Agent identity
Every agent invocation records:
- [ ] agent type.
- [ ] version.
- [ ] prompt version.
- [ ] model/provider.
- [ ] input evidence IDs.
- [ ] decision.
- [ ] confidence.
- [ ] policy result.
- [ ] action.
- [ ] outcome.

**Commit:** `security: add auditable agent identity and decisions`

## Task 12.2 — Prompt security
- [ ] Treat logs as untrusted input.
- [ ] Defend against prompt injection through log/issue content.
- [ ] Never allow telemetry text to redefine system policy.
- [ ] Separate instructions from evidence.
- [ ] Sanitize rendered Markdown/HTML.
- [ ] Limit tool arguments.
- [ ] Validate all structured tool outputs.

**Commit:** `security: harden agents against untrusted telemetry input`

## Task 12.3 — Tool authorization
- [ ] Explicit allowlist of tools.
- [ ] Per-agent permission sets.
- [ ] Read-only default.
- [ ] Production mutation capability disabled unless approved.
- [ ] Audit every tool invocation.

**Commit:** `security: enforce least-privilege agent tools`

## Task 12.4 — Audit trail
- [ ] Append-only logical audit events.
- [ ] Actor.
- [ ] Timestamp.
- [ ] Correlation ID.
- [ ] Before/after state.
- [ ] Approval record.
- [ ] Tool execution result.

**Commit:** `feat: add immutable-style audit event records`

---

# 17. Phase 13 — Database Reliability

## Task 13.1 — PostgreSQL schema and migrations
- [ ] Versioned migrations.
- [ ] Foreign keys.
- [ ] Constraints.
- [ ] Indexes.
- [ ] Audit tables.
- [ ] Incident tables.
- [ ] Agent execution tables.
- [ ] Idempotency keys.

**Tests:** migration-up, migration-down where supported, and schema integrity tests.

**Commit:** `feat: add versioned PostgreSQL schema`

## Task 13.2 — Repository/service separation
- [ ] Keep SQL/data-access separate from business logic.
- [ ] Add repository interfaces.
- [ ] Add transaction boundaries.
- [ ] Add idempotency handling.

**Commit:** `refactor: separate persistence from service logic`

## Task 13.3 — Isolation-friendly contracts
Provide lightweight contract tests using test doubles for core repositories.

Keep real PostgreSQL integration tests as a separate CI job.

This directly addresses the evaluation concern about integration tests depending on live MySQL/Redis-style services for the core suite.

**Commit:** `test: add database repository contract tests`

---

# 18. Phase 14 — Redis and Asynchronous Processing

## Task 14.1 — Queue model
- [ ] Job schema.
- [ ] Retry count.
- [ ] Visibility timeout.
- [ ] Dead-letter handling.
- [ ] Idempotency.
- [ ] Job correlation IDs.

**Commit:** `feat: add reliable asynchronous job processing`

## Task 14.2 — Worker
- [ ] Agent execution worker.
- [ ] Retry policy.
- [ ] Backoff.
- [ ] Poison-job handling.
- [ ] Graceful shutdown.
- [ ] Worker health endpoint.

**Tests:** queue contract + worker integration tests.

**Commit:** `feat: implement agent worker`

---

# 19. Phase 15 — Testing Strategy

## 15.1 Unit tests
- [ ] Services.
- [ ] Policies.
- [ ] schemas.
- [ ] anomaly detection.
- [ ] evidence correlation.
- [ ] prompt/output parsing.
- [ ] GitHub adapter logic.
- [ ] Kubernetes adapter logic.
- [ ] cost calculations.

## 15.2 Contract tests
- [ ] API schemas.
- [ ] repository interfaces.
- [ ] GitHub adapter.
- [ ] Kubernetes adapter.
- [ ] Prometheus adapter.
- [ ] LLM provider interface.

## 15.3 Integration tests
Use real ephemeral services in CI:
- [ ] PostgreSQL.
- [ ] Redis.
- [ ] OTel Collector.
- [ ] Prometheus where practical.

## 15.4 End-to-end tests
Scenario:

```text
Deploy demo version A
        ↓
Generate traffic
        ↓
Deploy version B containing controlled fault
        ↓
Telemetry detects degradation
        ↓
Alert is generated
        ↓
Incident created
        ↓
Agent gathers evidence
        ↓
Diagnosis produced
        ↓
Remediation proposed
        ↓
Approval simulated
        ↓
PR/remediation action generated
        ↓
Validation completes
```

## 15.5 Agent evaluation tests
Create fixed incident fixtures:
- [ ] high 5xx rate after deployment.
- [ ] database connection failure.
- [ ] Redis unavailable.
- [ ] pod crash loop.
- [ ] memory pressure.
- [ ] latency regression.
- [ ] telemetry missing/ambiguous evidence.
- [ ] malicious prompt injection embedded in logs.

Each fixture should define expected:
- [ ] evidence used.
- [ ] diagnosis category.
- [ ] uncertainty behavior.
- [ ] safe action boundary.

## 15.6 Security tests
- [ ] secret scanning.
- [ ] dependency vulnerability scanning.
- [ ] container scanning.
- [ ] IaC scanning.
- [ ] API authorization tests.
- [ ] SSRF protection tests where tools accept URLs.
- [ ] prompt-injection test fixtures.
- [ ] malicious GitHub issue/body fixtures.
- [ ] Kubernetes RBAC tests.

## 15.7 Resilience/chaos tests
- [ ] kill pod.
- [ ] add latency.
- [ ] break Redis.
- [ ] break DB.
- [ ] fail deployment.
- [ ] remove telemetry temporarily.

The expected platform behavior must be documented before enabling chaos tests.

**Commit sequence:** keep testing work incremental; do not add all tests in one giant commit.

---

# 20. Phase 16 — CI Pipeline

## Task 16.1 — Fast quality gate
Run on PR:
- [ ] formatting.
- [ ] lint.
- [ ] type-check.
- [ ] unit tests.
- [ ] coverage gate.
- [ ] package checks.

**Commit:** `ci: add fast application quality gates`

## Task 16.2 — Security gate
- [ ] secret scan.
- [ ] dependency audit.
- [ ] dependency review.
- [ ] container scan.
- [ ] static analysis.
- [ ] SBOM generation.
- [ ] license policy if desired.

**Commit:** `ci: add security quality gates`

## Task 16.3 — Kubernetes validation
- [ ] render manifests.
- [ ] kubeconform.
- [ ] kube-linter.
- [ ] policy validation.
- [ ] image reference validation.

**Commit:** `ci: validate Kubernetes manifests and policies`

## Task 16.4 — Terraform validation
- [ ] terraform fmt.
- [ ] terraform init -backend=false.
- [ ] terraform validate.
- [ ] provider lock verification.
- [ ] Trivy config scan.
- [ ] optional plan in controlled environment.

**Commit:** `ci: validate and scan Terraform`

## Task 16.5 — Build images
- [ ] Build backend image.
- [ ] Build frontend image.
- [ ] Build worker/agent images.
- [ ] Tag with commit SHA.
- [ ] Push only from trusted branch/tag.
- [ ] Generate SBOM.
- [ ] Scan before publication.

**Commit:** `ci: build and scan release images`

## Task 16.6 — E2E Kubernetes CI
Use an ephemeral cluster in CI:
- [ ] create cluster.
- [ ] deploy platform.
- [ ] deploy demo app.
- [ ] wait for readiness.
- [ ] execute smoke tests.
- [ ] execute incident simulation.
- [ ] collect logs/artifacts.
- [ ] destroy cluster.

**Commit:** `ci: add ephemeral Kubernetes end-to-end validation`

---

# 21. Phase 17 — CD / Release

## Task 17.1 — Versioning
- [ ] semantic versioning policy.
- [ ] release notes.
- [ ] changelog automation.
- [ ] immutable image tags.
- [ ] signed release metadata where practical.

**Commit:** `release: establish versioning and release metadata`

## Task 17.2 — Staging deployment
- [ ] Deploy only from protected branch/tag.
- [ ] Run post-deploy smoke tests.
- [ ] Record deployment metadata.
- [ ] Emit deployment event to observability platform.

**Commit:** `cd: deploy verified releases to staging`

## Task 17.3 — Production approval gate
- [ ] Manual approval.
- [ ] SLO/error-budget checks.
- [ ] Security scan status required.
- [ ] Rollback artifact available.
- [ ] Change record linked to release.

**Commit:** `cd: require governed production promotion`

## Task 17.4 — Rollback path
- [ ] Rollback command/runbook.
- [ ] Automated detection of failed rollout.
- [ ] Recommendation generated by agent.
- [ ] Human approval for production rollback.
- [ ] Post-rollback verification.

**Commit:** `cd: add auditable rollback workflow`

---

# 22. Phase 18 — Kubernetes and Production Runbooks

Create runbooks for:
- [ ] High 5xx rate.
- [ ] High latency.
- [ ] CrashLoopBackOff.
- [ ] OOMKilled.
- [ ] Failed deployment.
- [ ] DB unavailable.
- [ ] Redis unavailable.
- [ ] OTel pipeline failure.
- [ ] Prometheus failure.
- [ ] Agent failure.
- [ ] GitHub API outage.
- [ ] LLM provider outage.
- [ ] Accidental bad remediation.

Each runbook contains:
- symptoms.
- diagnostics.
- likely causes.
- safe commands/read-only checks.
- remediation options.
- approval requirements.
- rollback.
- verification.
- escalation.

**Commit:** `docs: add production incident runbooks`

---

# 23. Phase 19 — Disaster Recovery

Document and test:
- [ ] PostgreSQL backup strategy.
- [ ] restore procedure.
- [ ] Redis recovery expectations.
- [ ] Kubernetes rebuild.
- [ ] Terraform state recovery.
- [ ] secret restoration.
- [ ] audit-data retention.
- [ ] RTO.
- [ ] RPO.

At least one CI/manual verification workflow should test a non-production recovery path.

**Commit:** `feat: document and verify disaster recovery procedures`

---

# 24. Phase 20 — Documentation Set

README must include:
- [ ] one-paragraph purpose.
- [ ] architecture diagram.
- [ ] component list.
- [ ] quick start.
- [ ] exact prerequisites.
- [ ] environment variables.
- [ ] architecture flow.
- [ ] test commands.
- [ ] CI explanation.
- [ ] deployment process.
- [ ] security model.
- [ ] agent safety model.
- [ ] SLO examples.
- [ ] incident example.
- [ ] troubleshooting.
- [ ] repository tree.

Additional docs:
- [ ] Architecture.
- [ ] ADRs.
- [ ] API/OpenAPI.
- [ ] Data model.
- [ ] Kubernetes.
- [ ] Terraform.
- [ ] CI/CD.
- [ ] Observability.
- [ ] Testing.
- [ ] Security.
- [ ] Threat model.
- [ ] Agent operations.
- [ ] Incident lifecycle.
- [ ] Cost optimization.
- [ ] Governance.
- [ ] DR.
- [ ] Runbooks.

## Fresh-clone documentation test

A dedicated CI job should:
1. Start from a clean runner.
2. Checkout the repository.
3. Install exactly documented dependencies.
4. Run the documented verification command.
5. Build required images.
6. Execute the smoke suite.
7. Fail when README instructions are wrong.

**Commit:** `docs: verify and document the complete fresh-clone workflow`

---

# 25. Phase 21 — Threat Model

Create a threat model covering:

- [ ] compromised GitHub token.
- [ ] malicious dependency.
- [ ] malicious container image.
- [ ] prompt injection in logs.
- [ ] prompt injection in GitHub issues.
- [ ] poisoned telemetry.
- [ ] LLM provider compromise.
- [ ] excessive agent permissions.
- [ ] replayed approval.
- [ ] duplicate remediation.
- [ ] confused-deputy behavior.
- [ ] Kubernetes privilege escalation.
- [ ] secret leakage.
- [ ] data exfiltration.
- [ ] model hallucination.
- [ ] unsafe rollback.
- [ ] denial of service against agent worker.

For each threat:
- trust boundary.
- attack path.
- prevention.
- detection.
- mitigation.
- residual risk.

**Commit:** `docs: add platform threat model`

---

# 26. Phase 22 — Performance and Reliability

## Task 22.1 — API performance
- [ ] Define baseline latency targets.
- [ ] Add load-test scenario.
- [ ] Add performance regression gate for critical endpoints.

## Task 22.2 — Queue performance
- [ ] Measure throughput.
- [ ] Measure queue latency.
- [ ] Measure agent execution latency.

## Task 22.3 — Agent budget controls
- [ ] Token budget.
- [ ] maximum reasoning/tool iterations.
- [ ] timeout.
- [ ] maximum evidence payload.
- [ ] cost ceiling per incident.

**Commit:** `feat: enforce reliability and cost budgets for agents`

---

# 27. Phase 23 — Agent Evaluation and Regression Harness

Build an evaluation suite separate from ordinary unit tests.

For each fixture record:
- incident input.
- telemetry evidence.
- expected diagnosis categories.
- forbidden unsafe actions.
- acceptable uncertainty range.
- required citations/evidence.
- execution cost.
- latency.

Track:
- [ ] diagnosis accuracy.
- [ ] evidence grounding.
- [ ] unsafe-action rate.
- [ ] false-positive rate.
- [ ] cost per incident.
- [ ] latency.

Do not allow a model/prompt change to silently reduce safety.

**Commit:** `test: add agent evaluation and regression harness`

---

# 28. Phase 24 — Observability for the Platform Itself

Instrument:
- [ ] API.
- [ ] workers.
- [ ] agents.
- [ ] LLM calls.
- [ ] GitHub calls.
- [ ] Kubernetes API calls.
- [ ] queue processing.
- [ ] database operations.

Dashboards should show:
- [ ] agent success/failure.
- [ ] average cost.
- [ ] tool calls.
- [ ] approval latency.
- [ ] incident MTTR.
- [ ] evidence retrieval failures.
- [ ] model/provider failure rate.

**Commit:** `feat: instrument agent control plane`

---

# 29. Phase 25 — Final End-to-End Demonstration

Create a deterministic demonstration scenario that a reviewer can reproduce from CI.

## Scenario

1. Deploy healthy application.
2. Run smoke test.
3. Capture baseline telemetry.
4. Deploy intentionally faulty revision.
5. Generate synthetic traffic.
6. Trigger alert.
7. Create incident automatically.
8. Query logs/metrics/traces/Kubernetes state.
9. Correlate deployment and telemetry changes.
10. Run AI diagnosis.
11. Produce evidence-backed root cause.
12. Generate remediation proposal.
13. Run risk/policy checks.
14. Require simulated human approval.
15. Create GitHub issue.
16. Create remediation PR.
17. Run CI against PR.
18. Verify safe remediation.
19. Record incident resolution.
20. Generate incident summary.

Store sanitized, deterministic evidence as test fixtures.

**Commit:** `test: add reproducible end-to-end incident demonstration`

---

# 30. Phase 26 — DataFactor-Focused Quality Sweep

Based directly on the supplied DataFactor review feedback:

## Fresh-clone reliability
- [ ] Verify install/build/test on a clean CI runner.
- [ ] Ensure all required lockfiles are committed.
- [ ] Make the exact verification command obvious.
- [ ] Confirm README steps match actual CI commands.
- [ ] Remove hidden dependency on developer machine state.

The supplied review explicitly emphasized fresh-clone install/build/test as a major value driver. fileciteturn0file0L87-L92

## Incremental engineering history
- [ ] Maintain meaningful small commits throughout real development.
- [ ] Pair source changes with tests.
- [ ] Use issues/PRs for non-trivial changes.
- [ ] Avoid one giant final commit.
- [ ] Avoid artificial/backdated commits.

The supplied review specifically identified bursty one-day history and recommended real incremental test-paired changes and reviewable issues/PRs. fileciteturn0file0L93-L98

## Testability
- [ ] Keep fast unit/contract tests independent of live services.
- [ ] Keep real-service integration suites separately executable in CI.
- [ ] Document how each test tier works.

The supplied review recommended an isolation-friendly contract-test layer while retaining real MySQL/Redis integration coverage in CI. fileciteturn0file0L105-L110

## Infrastructure depth
- [ ] Reusable Terraform modules.
- [ ] Environment separation.
- [ ] Provider/module pinning.
- [ ] `.terraform.lock.hcl`.
- [ ] IaC policy scanning.
- [ ] Kubernetes policy validation.
- [ ] Infrastructure tests.

The supplied review called out limited IaC reuse/depth and specifically recommended provider/module pinning and committing `.terraform.lock.hcl`. fileciteturn0file0L117-L122

## CI/CD
Ensure CI visibly proves:
- [ ] lint.
- [ ] format.
- [ ] type-check.
- [ ] unit tests.
- [ ] integration tests.
- [ ] dependency audit.
- [ ] container scan.
- [ ] Kubernetes validation.
- [ ] Terraform validation.
- [ ] E2E.
- [ ] artifact publication.

The supplied review highlighted CI coverage across backend/frontend/SQL/Kubernetes/Terraform and image build, while noting that automated detection did not clearly confirm some gates. Make the actual workflow behavior unambiguous. fileciteturn0file0L69-L80

---

# 31. Recommended Commit Roadmap

Do not create these commits artificially. Use this as the logical order for genuine work.

### Foundation
1. `chore: establish repository governance`
2. `chore: define language and tooling standards`
3. `chore: make dependency resolution reproducible`
4. `docs: define platform architecture`
5. `docs: add architecture decision records`
6. `feat: add versioned platform contracts`

### Demo workload
7. `feat: add observable FastAPI demo service`
8. `test: add backend unit and contract coverage`
9. `feat: add demo web frontend`
10. `test: add frontend component coverage`
11. `build: harden application containers`

### Kubernetes/IaC
12. `feat: deploy demo application to Kubernetes`
13. `feat: add Kubernetes environment overlays`
14. `security: enforce Kubernetes workload hardening`
15. `feat: establish Terraform infrastructure structure`
16. `refactor: introduce reusable Terraform modules`
17. `chore: pin Terraform providers and enforce IaC reproducibility`

### Observability
18. `feat: instrument services with OpenTelemetry`
19. `feat: add OpenTelemetry collector pipeline`
20. `feat: define platform and application metrics`
21. `feat: add operational Grafana dashboards`
22. `feat: add SRE alert rules`
23. `feat: define service level objectives`

### Incident platform
24. `feat: add incident persistence model`
25. `feat: implement incident lifecycle API`
26. `test: add incident state-machine coverage`
27. `feat: add reliable asynchronous job processing`
28. `feat: implement agent worker`

### AI
29. `feat: add provider-agnostic LLM interface`
30. `feat: add bounded incident evidence retrieval`
31. `feat: implement incident analysis agent`
32. `feat: add telemetry anomaly detection`
33. `feat: add evidence-based root cause analysis`
34. `test: add agent fixture evaluation`

### Governance/remediation
35. `feat: generate governed remediation proposals`
36. `security: add remediation policy engine`
37. `feat: require human approval for production actions`
38. `security: add auditable agent identity and decisions`
39. `security: harden agents against untrusted telemetry input`
40. `security: enforce least-privilege agent tools`
41. `feat: add immutable-style audit event records`

### GitHub automation
42. `feat: add GitHub integration adapter`
43. `feat: create evidence-backed GitHub incident issues`
44. `feat: open governed remediation pull requests`

### Reliability/cost
45. `feat: collect cost optimization evidence`
46. `feat: add cost optimization recommendations`
47. `feat: enforce reliability and cost budgets for agents`

### CI/CD
48. `ci: add fast application quality gates`
49. `ci: add security quality gates`
50. `ci: validate Kubernetes manifests and policies`
51. `ci: validate and scan Terraform`
52. `ci: build and scan release images`
53. `ci: add ephemeral Kubernetes end-to-end validation`
54. `release: establish versioning and release metadata`
55. `cd: deploy verified releases to staging`
56. `cd: require governed production promotion`
57. `cd: add auditable rollback workflow`

### Docs/operations
58. `docs: add production incident runbooks`
59. `feat: document and verify disaster recovery procedures`
60. `docs: add platform threat model`
61. `feat: instrument agent control plane`
62. `test: add agent evaluation and regression harness`
63. `test: add reproducible end-to-end incident demonstration`
64. `docs: verify and document the complete fresh-clone workflow`

The exact number of commits should follow actual work, not a target. A single task may legitimately require multiple commits; unrelated work should not be bundled merely to increase commit count.

---

# 32. CI Job Matrix

Recommended workflow separation:

```text
pull_request
├── quality
│   ├── format
│   ├── lint
│   ├── typecheck
│   └── unit-tests
│
├── security
│   ├── secret-scan
│   ├── dependency-review
│   ├── dependency-audit
│   └── sast
│
├── containers
│   ├── build
│   ├── scan
│   └── sbom
│
├── kubernetes
│   ├── render
│   ├── kubeconform
│   ├── kube-linter
│   └── policy
│
├── terraform
│   ├── fmt
│   ├── init
│   ├── validate
│   ├── lock-check
│   └── trivy-config
│
├── integration
│   ├── postgres
│   ├── redis
│   └── telemetry
│
└── e2e
    ├── ephemeral-k8s
    ├── deploy
    ├── smoke
    ├── incident-simulation
    └── artifact-collection
```

---

# 33. Minimum Required Quality Gates Before Submission

Do not submit until all of these are true:

### Build/reproducibility
- [ ] Clean CI runner can install all dependencies.
- [ ] All lockfiles are committed.
- [ ] Images build from scratch.
- [ ] README commands match reality.

### Tests
- [ ] Unit tests run automatically.
- [ ] Contract tests run automatically.
- [ ] Integration tests run against ephemeral services.
- [ ] E2E test runs against an ephemeral Kubernetes cluster.
- [ ] Agent regression suite runs automatically.
- [ ] Coverage threshold is enforced.

### Security
- [ ] No secrets committed.
- [ ] Secret scan passes.
- [ ] Dependencies scanned.
- [ ] Containers scanned.
- [ ] Terraform/IaC scanned.
- [ ] Kubernetes manifests scanned.
- [ ] Least privilege documented.
- [ ] Agent tools are allowlisted.
- [ ] Human approval blocks production mutation.

### Infrastructure
- [ ] Terraform format/validate passes.
- [ ] Terraform lockfile committed.
- [ ] Modules are reusable and version-pinned.
- [ ] Kubernetes manifests are schema-valid.
- [ ] Kubernetes policies pass.

### Observability
- [ ] Logs, metrics, traces work.
- [ ] Correlation IDs work.
- [ ] Alerts fire from controlled faults.
- [ ] Incident agent can consume bounded evidence.

### Agent correctness
- [ ] Agent can say "insufficient evidence."
- [ ] Agent cannot directly mutate production.
- [ ] Agent outputs are schema validated.
- [ ] Agent decisions are auditable.
- [ ] Prompt injection fixture is handled safely.
- [ ] Tool calls are authorized and logged.

### Operations
- [ ] Incident runbooks exist.
- [ ] Rollback path exists.
- [ ] DR documentation exists.
- [ ] SLO/error-budget model exists.

---

# 34. Suggested Agent Sequence

Use coding agents in this order:

1. **Repository Architect Agent**
   - scaffolding, ADRs, contracts, repository layout.

2. **Application Agent**
   - FastAPI/Next.js demo workload, tests, Docker.

3. **Platform/IaC Agent**
   - Kubernetes, Terraform, policies, CI validation.

4. **Observability Agent**
   - OpenTelemetry, Prometheus, Grafana, alerts, SLOs.

5. **Backend Reliability Agent**
   - PostgreSQL, Redis, workers, migrations, contracts.

6. **AI Agent Runtime Agent**
   - LLM adapter, evidence retrieval, diagnosis, anomaly detection.

7. **Safety/Governance Agent**
   - permissions, policy engine, approval workflow, audit trail.

8. **GitHub Automation Agent**
   - issues, PRs, checks, deployment metadata.

9. **Security Agent**
   - threat model, secret scanning, SAST, dependency/container/IaC security.

10. **QA/E2E Agent**
    - integration, Kubernetes e2e, incident simulations, agent regression tests.

11. **SRE/Operations Agent**
    - runbooks, DR, SLOs, rollback, cost controls.

12. **Release/Review Agent**
    - fresh-clone validation, documentation audit, CI audit, repository consistency sweep.

---

# 35. Final Review Checklist for the Release Agent

Before submission, inspect the entire repository rather than only the newest feature.

- [ ] README is complete and tested.
- [ ] No broken documentation links.
- [ ] No stale architecture diagrams.
- [ ] No undocumented environment variable.
- [ ] No undocumented API endpoint.
- [ ] No unused dependency.
- [ ] No dead code introduced by refactoring.
- [ ] No giant files that could be decomposed.
- [ ] No duplicate business logic.
- [ ] No secrets or generated credentials.
- [ ] No Terraform state.
- [ ] No unpinned critical infrastructure dependencies.
- [ ] `.terraform.lock.hcl` committed.
- [ ] CI gates actually execute the tools they claim to execute.
- [ ] Test reports are uploaded as CI artifacts.
- [ ] Failed e2e runs preserve diagnostic logs.
- [ ] Security jobs are required checks.
- [ ] Production changes require approval.
- [ ] Agent decisions are auditable.
- [ ] Rollback procedure is documented.
- [ ] Fresh-clone CI path succeeds.
- [ ] Final end-to-end incident scenario succeeds.
- [ ] Changelog reflects the shipped release.
- [ ] Release tag is created only after all gates pass.

---

# 36. What the Reviewer Should Be Able to See

A strong final repository should make this journey obvious:

```text
A fresh CI runner
    ↓
reproducible dependency install
    ↓
lint + type-check + security checks
    ↓
unit/contract/integration tests
    ↓
container build + scan + SBOM
    ↓
Terraform + Kubernetes validation
    ↓
ephemeral Kubernetes deployment
    ↓
OpenTelemetry telemetry
    ↓
Prometheus/Grafana + alerts
    ↓
controlled incident injection
    ↓
incident creation
    ↓
bounded evidence retrieval
    ↓
AI diagnosis with evidence + confidence
    ↓
policy evaluation
    ↓
human approval
    ↓
GitHub issue / remediation PR
    ↓
CI verifies proposed change
    ↓
safe deployment / rollback
    ↓
incident resolution + audit trail
```

That end-to-end, reproducible story is more important than adding dozens of disconnected AI features.
