# Governance

This document defines how the repository is governed: who can change what, which checks are required,
how history is expected to look, and how branch protection must be configured on GitHub. It is the
authority referenced by [CONTRIBUTING.md](../CONTRIBUTING.md) and enforced by CI.

## Roles

| Role | Responsibility | GitHub permission |
| --- | --- | --- |
| Maintainer | Owns architecture, security, governance, releases and final review | Admin on the repository; required reviewer via `.github/CODEOWNERS` |
| Contributor | Proposes changes through issues and pull requests | Write through pull requests; no direct push to `main` |
| Automation (agents, bots) | Opens issues/PRs, runs pipelines, reports findings | `GITHUB_TOKEN` scoped per workflow, `contents: read` by default, `pull-requests: write` only where explicitly required |

The repository owner (`@Kaoserahamed`) is the current maintainer and the only required code owner. The
model is deliberately single-maintainer-friendly but keeps every guardrail that matters once additional
maintainers join: ownership is path-based, so a new maintainer only needs to be added to
`.github/CODEOWNERS` and a GitHub team.

## Branch model and history expectations

- `main` is the only long-lived branch and is always deployable.
- Work happens on short-lived branches named `feat/…`, `fix/…`, `chore/…`, `docs/…`, `security/…`,
  `ci/…`, `test/…` or `refactor/…`.
- History is linear and meaningful: merge commits with Conventional Commit subjects are preferred over
  squashes, so the real sequence of reviewed changes is preserved.
- One logical change per commit. Never manufacture, backdate or artificially fragment commits to make
  history look busier: commits must correspond to work actually performed.
- Release tags follow semantic versioning (`vMAJOR.MINOR.PATCH`) and are created only after every
  required gate passes on `main`.

## Required status checks on `main`

The following jobs must pass before merge. Security jobs are required, not advisory. Job names are the
`name:` values of the jobs in `.github/workflows/`.

| Workflow | Job | Purpose |
| --- | --- | --- |
| `repo-policy.yml` | `repository-policy` | Governance files present, no forbidden tracked files, actions pinned by SHA |
| `repo-policy.yml` | `markdown-links` | Local and external documentation links resolve |
| `ci.yml` | `quality` | Format, lint, type-check, unit tests, coverage gate |
| `ci.yml` | `contract` | Schema and adapter contract tests against fakes |
| `security.yml` | `secret-scan` | No credentials ever committed |
| `security.yml` | `dependency-audit`, `dependency-review` | Known vulnerable or disallowed dependencies |
| `security.yml` | `sast` | Static analysis of Python and TypeScript |
| `container.yml` | `build-and-scan` | Images build from scratch, scan clean, SBOM published |
| `k8s.yml` | `validate` | Render, schema validation, policy checks, image reference validation |
| `terraform.yml` | `validate` | `fmt`, `init -backend=false`, `validate`, lockfile drift, IaC scan |
| `e2e.yml` | `ephemeral-k8s` | Deploy to an ephemeral cluster, smoke test, incident simulation |

## Repository policy enforcement in CI

`.github/workflows/repo-policy.yml` runs `scripts/check_repo_policy.py`, which fails the build when:

1. a required governance file is missing;
2. a forbidden artifact is tracked by git (`.env`, Terraform state/plan files, kubeconfigs, private keys,
   downloaded providers, generated scan output);
3. a third-party GitHub Action is not pinned to a full 40-character commit SHA;
4. a relative Markdown link points at a file that does not exist;
5. `.github/CODEOWNERS` has no default catch-all rule.

The same script runs locally with `python scripts/check_repo_policy.py`.

## Change management

1. Open an issue using the matching template (feature, bug, incident, security, architecture decision).
2. Implement the change on a branch and open a pull request that references the issue.
3. Complete the pull request template, including verification evidence and the security checklist.
4. CI runs the gates above; the repository policy, security and quality jobs are required checks.
5. A code owner approves. The author does not self-approve changes to `main`.
6. Merge with a merge commit whose subject is a Conventional Commit.
7. Update `CHANGELOG.md` under `Unreleased`; a release moves those entries under the released version.

### Exceptions

- Documentation-only typo fixes still require CI but may use a single-commit branch.
- Emergency rollbacks follow the operations runbooks (`docs/20-runbooks/`) with explicit human approval.
  The incident issue records the approval, the action hash and the result, and a follow-up pull request
  reconciles the repository state.
- CI is never bypassed to make a failing change pass. If a gate is wrong, the gate is fixed in its own
  reviewed change with the reason documented.

## Dependency management

### Pinning policy

| Dependency class | Pin | Rationale |
| --- | --- | --- |
| Python runtime dependencies | Range in `pyproject.toml`, exact versions in `uv.lock` | The lockfile is authoritative; CI installs with `uv sync --frozen` so a stale lockfile fails the build |
| Python developer tooling | Exact `==` pins in `[project.optional-dependencies].dev` | Tool behaviour differences must not silently change gate outcomes |
| JavaScript dependencies | Exact versions in `package.json`, full graph in `package-lock.json`, installed with `npm ci` | Reproducible resolution on a fresh runner |
| GitHub Actions | Full 40-character commit SHA plus a `# vX.Y.Z` comment | Tags are mutable; SHAs are not, and the comment keeps the version reviewable |
| Terraform providers and modules | Exact version constraints plus committed `.terraform.lock.hcl` | Reproducible plans; drift is detected in CI |
| Container base images | Pinned tag with digest in the final image reference | Immutable deployments |
| Go modules (if a Go component is added) | `go.mod` with exact versions and a committed `go.sum` | Reproducible builds |

Unpinned critical dependencies are treated as a defect: CI fails when `uv.lock` is stale (`--frozen`),
when `package-lock.json` and `package.json` disagree (`npm ci`), or when an action is not SHA-pinned
(`scripts/check_repo_policy.py`).

### Update channels

| Channel | Cadence | Process |
| --- | --- | --- |
| Security updates | As soon as a GitHub advisory or scanner finding lands | Dependabot security update, or a manual fix; treated as priority work with a `security:` commit |
| Patch and minor updates | Weekly, grouped by ecosystem (Dependabot) | Reviewed against the upgrade procedure below |
| Major updates | Deliberately, on demand | Automation ignores them; see the upgrade procedure |
| Tool and runtime upgrades (Python/Node/uv) | When a supported version reaches end of support | Reviewed change updating `pyproject.toml`, `package.json` engines, CI matrix and `docs/03-local-development.md` |

`.github/dependabot.yml` also applies a **cooldown** (currently three days) before a newly published
version is proposed, so a compromised or immediately withdrawn release does not reach the repository
before the ecosystem notices it.

### Upgrade procedure

1. Confirm the target version: read the upstream changelog or advisory, and decide whether the update is
   security-driven, routine or a deliberate major.
2. Update the manifest, not just the lockfile: `pyproject.toml` / `package.json` for direct dependencies.
3. Regenerate the lockfile with the pinned tool: `uv lock` (or `uv lock --upgrade-package <name>`) and
   `npm install --package-lock-only`; for infrastructure, `terraform init -upgrade` inside the affected
   root.
4. Review the lockfile diff explicitly. Transitive additions, removals and platform markers must be
   explainable; if they are not, the update is not ready.
5. Run the full local gate: `make verify`, plus `make test-integration` when the dependency touches the
   database, queue, telemetry or HTTP stack.
6. Update documentation in the same change when behaviour, configuration or required runtime versions
   change (`docs/03-local-development.md`, `docs/04-configuration.md`, `.env.example`, `CHANGELOG.md`).
7. For a major upgrade, add or update an ADR that records the migration risk, the rollback plan and the
   validation evidence.
8. Open the pull request with the lockfile diff included, and let CI run every gate. Never merge an
   upgrade that disables or weakens a gate to pass.

## Governance of agent automation

- Every agent invocation is recorded with agent type and version, prompt version, model/provider, input
  evidence IDs, decision, confidence, policy result, action and outcome (see the audit trail phase).
- Agents may open issues and pull requests, comment on them, and produce diagnoses, proposals and
  cost recommendations.
- Agents may never push to `main`, approve their own pull requests, merge pull requests, or mutate
  production state directly.
- Production-changing actions require all of the following: a policy pass (allowlist, blocked namespaces,
  rate limits, blast radius), an unexpired approval bound to the action hash, and an audit record with
  before/after state.
- A model, prompt or tool-permission change requires the agent evaluation suite to pass, including the
  fixtures that assert unsafe actions are refused, and a threat-model update when a trust boundary moves.
- Agent budgets (tokens, iterations, wall-clock timeout, evidence payload size, cost per incident) are
  enforced in code, not by prompt instruction.

