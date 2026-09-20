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
