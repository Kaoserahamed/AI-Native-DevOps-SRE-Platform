# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Release policy

- Versions are identical for the platform API, agent images and Kubernetes manifests: one release trains
  all artifacts.
- Every release is published from a protected tag on `main` after the full CI gate (quality, security,
  Kubernetes, Terraform, integration, e2e) passes, and the release notes link the artifacts, SBOMs and
  the linked change records.
- Container images are referenced by immutable digests and semantic version tags; `latest` is never used
  in a deployment manifest.
- Breaking changes to published contracts (`packages/contracts`) require a new schema version, a
  migration note in `docs/06-data-model.md` and a changelog entry under `Changed`.

## [Unreleased]

### Added

- Repository governance: README, LICENSE, contributing guide, code of conduct, security policy, changelog,
  CODEOWNERS, pull request and issue templates, and documented branch-protection recommendations.
- Tooling standards: `pyproject.toml` (ruff, strict mypy, pytest tiers, coverage gate), flat ESLint
  configuration, Prettier configuration, shared strict `tsconfig.base.json`, `.editorconfig`,
  `.pre-commit-config.yaml`, `.golangci.yml` and the `Makefile` verification entry points.
- Repository policy automation: `scripts/check_repo_policy.py` with unit tests, plus the
  `repo-policy.yml` workflow that also checks documentation links.
- Local development documentation with supported runtime versions, tool pinning locations and Windows
  equivalents for every `make` target (`docs/03-local-development.md`).
- Reproducible dependency management: committed `uv.lock` and `package-lock.json` lockfiles, a documented
  pinning policy and upgrade procedure, and Dependabot configuration with grouped updates and a release
  cooldown for the `uv`, `npm` and `github-actions` ecosystems.
- Platform overview and architecture specification: purpose, non-goals, engineering principles, control
  loop, system context and component diagrams, control-plane versus data-plane responsibilities, trust
  boundaries, synchronous/asynchronous interaction matrix and failure-domain analysis
  (`docs/00-overview.md`, `docs/01-architecture.md`).
- Observable FastAPI demo service: health/readiness probes, Prometheus metrics, structured JSON logs,
  request correlation IDs, PostgreSQL and Redis integration, a development-only controllable failure
  mode, graceful shutdown and validated environment configuration, with unit, API contract and
  database integration tests (`services/demo_api`, `docs/04-configuration.md`, `.env.example`).
- ADR framework (`docs/adr/`) with a template, an indexed and immutable decision log, and the nine
  foundational decisions: Kubernetes deployment model, OpenTelemetry architecture, Prometheus/Grafana,
  PostgreSQL storage, Redis queue and cache, LLM provider abstraction, human approval model, GitHub
  integration and Terraform environment separation.
- Prometheus metric exposition tests: declared histogram bounds stay finite and ascending, every observed
  series exposes exactly one `+Inf` bucket, and the service info metric carries the identity labels the
  dashboards join on (`tests/demo_api/test_metrics.py`).
- Demo web frontend (`apps/demo-app/frontend`): a typed demo API client, a service status panel that
  separates liveness from readiness and treats a `503` readiness payload as a degraded result rather than a
  transport error, an items inventory panel with loading, error and empty states, request-correlation
  display, npm workspace wiring that installs from the single committed lockfile, and unit and component
  tests with an enforced coverage gate.
- Frontend tooling guarantees: `scripts/typecheck.mjs` now type-checks each workspace with the TypeScript
  version that workspace pins, and a documented configuration reference covers the frontend and explains
  why its variables must not live in the demo API's `.env`
  (`apps/demo-app/README.md`, `docs/03-local-development.md`, `docs/04-configuration.md`).

### Fixed

- `npm run format:check` succeeds on a clean checkout: the generated contract schemas are now excluded from
  Prettier, which disagreed with the generator that owns their formatting and therefore failed the gate.

[Unreleased]: https://github.com/Kaoserahamed/AI-Native-DevOps-SRE-Platform/commits/main
