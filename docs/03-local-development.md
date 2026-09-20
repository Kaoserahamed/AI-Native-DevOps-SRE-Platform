# Local development

This document is the single source of truth for the runtime versions, tool versions and commands the
repository expects. CI runs the same commands, so anything that passes locally with this toolchain
passes in CI, and a fresh clone never depends on machine state.

## Supported runtimes

| Runtime | Supported | Used in CI | Notes |
| --- | --- | --- | --- |
| Python | 3.11, 3.12, 3.13 (`requires-python = ">=3.11"`) | 3.12 | Pinned in `pyproject.toml`; the lockfile resolves for this range |
| Node.js | 20.19+ or 22 LTS (`engines.node >= 20.19.0`) | 20 | Required for repository tooling and the demo frontend |
| npm | 10+ (`engines.npm >= 10`) | bundled with Node 20 | `package-lock.json` is the authoritative dependency graph |
| `uv` | recent release (validated with 0.12.x) | installed by `astral-sh/setup-uv`, pinned by SHA | Resolves and installs Python dependencies from `uv.lock` |
| Go | not required today | inactive | See "Go components" below |
| Docker / Compose | Docker 24+, Compose v2 | ephemeral services in CI | Local PostgreSQL/Redis/OTel arrive with the demo application |
| Kubernetes tooling | `kubectl` 1.30+, `kustomize` 5+, `kubeconform`, `kube-linter` | pinned in `k8s.yml` | Manifests must validate before review |
| Terraform | 1.9+ with `fmt`, `validate`, `trivy config`, `tflint` | pinned in `terraform.yml` | Providers and modules are locked by `.terraform.lock.hcl` |

Where each version is pinned:

| Pin | File | Enforced by |
| --- | --- | --- |
| Python dependency graph | `uv.lock`, `pyproject.toml` | `uv sync --frozen` in CI and the `Makefile` |
| Python developer tools | `pyproject.toml` → `[project.optional-dependencies].dev` (exact `==` pins) | `uv sync --frozen --all-extras` |
| Node dependency graph | `package-lock.json`, `package.json` | `npm ci` in CI |
| Git hooks | `.pre-commit-config.yaml` `rev:` values | the CI quality job |
| GitHub Actions | workflow `uses:` pinned to full commit SHAs with a `# vX.Y.Z` comment | `scripts/check_repo_policy.py` |

## One-time setup

```bash
git clone https://github.com/Kaoserahamed/AI-Native-DevOps-SRE-Platform.git
cd AI-Native-DevOps-SRE-Platform
python -m pip install uv          # or: pipx install uv
uv sync --frozen --all-extras     # installs exactly the committed lockfile
uv run pre-commit install         # installs the pre-commit and commit-msg hooks
npm ci                            # repository Node tooling (eslint, prettier, typescript)
```

On Windows, keep Git from rewriting line endings so the formatters agree with the repository:

```powershell
git config core.autocrlf false
```

`.gitattributes` normalises text files to LF inside the repository regardless of the operating system.

## Canonical commands

The `make` targets are the canonical entry points; CI runs the same underlying commands.

| Goal | Command | Tool |
| --- | --- | --- |
| Install everything | `make bootstrap` | `uv sync --frozen --all-extras`, `pre-commit install` |
| Apply formatting | `make format` | `ruff format`, `ruff check --fix` |
| Verify formatting | `make format-check` | `ruff format --check` |
| Lint Python | `make lint` | `ruff check` |
| Type-check Python | `make typecheck` | `mypy` in strict mode |
| Fast tests (unit + contract) | `make test` | `pytest` with the coverage gate |
| Integration tests | `make test-integration` | `pytest -m integration` against ephemeral services |
| Agent evaluation suite | `make test-agent-eval` | `pytest -m agent_eval` |
| Repository policy | `make policy` | `scripts/check_repo_policy.py` |
| Frontend lint/format/type-check/tests | `make frontend` | `eslint`, `prettier`, `scripts/typecheck.mjs`, `vitest` with the coverage gate |
| Frontend production smoke test | `make frontend-smoke` | `next build`, then the standalone entrypoint against an in-process stub backend |
| Everything CI runs on a pull request | `make verify` | every fast gate above |

### Container builds

Image builds require Docker 24+ and are deliberately outside the fast gate: they take minutes, and CI
builds, scans and publishes them in the container job.

```bash
make build-images                                                        # both application images
docker build -f services/demo_api/Dockerfile -t demo-api:dev .           # demo API
docker build -f apps/demo-app/frontend/Dockerfile -t demo-frontend:dev . # demo frontend
```

Both Dockerfiles use the repository root as their build context (the Python project and the npm workspace
both live there); `.dockerignore` keeps local state, secrets and generated output out of that context.
Image scanning, SBOM generation and publication are part of the container workflow (Task 16.5).

### Windows equivalents

`make` is not installed by default on Windows. Run the same steps directly with PowerShell:

```powershell
uv sync --frozen --all-extras
uv run pre-commit run --all-files
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -m "not integration and not e2e and not chaos and not slow" --cov-fail-under=90
python scripts/check_repo_policy.py

# npm resolves local binaries through cmd.exe, which cannot handle an ampersand in the clone path.
# If your checkout path contains "&", use the direct invocation below; otherwise `npm run verify`.
node node_modules/eslint/bin/eslint.js .
node node_modules/prettier/bin/prettier.cjs --check .
node scripts/typecheck.mjs
node node_modules/vitest/vitest.mjs run --root apps/demo-app/frontend --coverage
node apps/demo-app/frontend/tests/e2e/smoke.mjs
```


## Tooling decisions

### Python

- One project, one lockfile: `services/`, `packages/` and `apps/` are importable namespaces that sit next
  to the root `pyproject.toml`, so `uv sync` installs the platform and the tooling in a single step.
- `ruff` replaces black, isort, flake8 and pyupgrade; configuration lives in `[tool.ruff]`.
- `mypy` runs in `strict` mode. Its `files` list grows with the repository: every new package is added in
  the same change that introduces it.
- `pytest` markers describe the test tiers, and a unit test must never need a live service. Integration and
  e2e tiers are separate targets so the fast gate stays fast.
- The coverage gate is enforced with `--cov-fail-under` in both the `Makefile` and CI.

### TypeScript and JavaScript

- `tsconfig.base.json` holds the shared strict compiler options; every workspace extends it.
- npm workspaces keep one dependency graph: `npm ci` at the repository root installs the repository
  tooling and every workspace (`apps/demo-app/frontend` today) from the committed `package-lock.json`.
- `eslint.config.mjs` is a flat configuration combining the recommended JavaScript and TypeScript rule sets
  with Prettier compatibility. It is deliberately not type-aware: `scripts/typecheck.mjs` performs strict
  type checking separately, so the lint gate stays fast and does not depend on which dependencies are
  installed.
- `scripts/typecheck.mjs` discovers every workspace `tsconfig.json` and builds it with the TypeScript
  version **that workspace pins**, falling back to the root compiler only when a workspace declares none.
  A workspace pinning an older compiler (for example one required by its framework) is therefore never
  checked by the root toolchain by accident.
- Workspace unit tests run with `vitest`; the demo frontend enforces coverage thresholds in
  `vitest.config.ts` (85% statements, branches, functions and lines) and runs them through
  `npm run verify`. Unit and component tests never need a live backend: they stub `fetch`.
- Prettier formats code and configuration; Markdown, infrastructure manifests and generated files are
  excluded in `.prettierignore` so formatting churn never hides a real change.

### Go components

The platform is implemented in Python and TypeScript, so no Go module exists today and `go.mod`/`go.sum`
are intentionally absent. `.golangci.yml` defines the lint policy a future Go component must satisfy, and
the CI job activates automatically once a module is committed. Adding Go (for example a high-throughput
traffic generator for the end-to-end incident scenario) requires `go.mod`, `go.sum`, tests and an update
to this document in the same change.

### Pre-commit hooks

`pre-commit` runs the fast gates before each commit: whitespace and end-of-file fixes, YAML/TOML/JSON
syntax checks, private-key detection, `ruff` and `ruff-format`, and the repository policy check. The strict
`mypy` hook lives in the `manual` stage because it is slower; run it with `make typecheck` or
`uv run pre-commit run --hook-stage manual mypy --all-files`.

## Environment variables

Phase 0 requires none. Configuration is introduced by the phase that needs it, together with an
`.env.example` entry and a row in `docs/04-configuration.md`. Never commit a real `.env` file:
`scripts/check_repo_policy.py` fails the build when one is tracked.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `uv sync --frozen` reports the lockfile is out of date | Dependencies changed without regenerating the lockfile | Run `uv lock` and commit `uv.lock` in the same change |
| `ruff format --check` fails only on Windows | Files were checked out with CRLF | `git config core.autocrlf false`, then re-normalise the working tree |
| `npm run <script>` fails with `'SRE' is not recognized` | The clone path contains `&`, which `cmd.exe` treats as a command separator | Use a clone path without `&`, or the direct Node invocation above |
| Prettier reports `Explicitly specified pattern "." is a symbolic link` | The working directory is a junction or symlink | Run Prettier from the real repository path |
| `mypy` reports a module found under two names | A directory lacks an explicit package boundary | Add `__init__.py` to the directory (as `scripts/` does) |
| `pytest` fails with `unrecognized arguments: --cov` | `pytest-cov` is not installed | `uv sync --frozen --all-extras` |
| `pre-commit` reports `no-commit-to-branch` | You are committing directly on `main` | Create a topic branch as required by `docs/18-governance.md` |
