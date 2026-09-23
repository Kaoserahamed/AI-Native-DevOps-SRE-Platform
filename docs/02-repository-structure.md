# Repository Structure

This document explains the repository organization and the purpose of each directory.

## Overview

The repository follows a monorepo structure with clear separation between applications, services, infrastructure, observability, and supporting packages.

```
ai-native-devops-sre/
├── apps/              # User-facing applications
├── services/          # Backend services and agents
├── packages/          # Shared libraries and contracts
├── infra/            # Infrastructure as Code
├── observability/    # Telemetry configuration
├── tests/            # Cross-cutting tests
├── docs/             # Documentation
├── scripts/          # Automation scripts
└── migrations/       # Database migrations
```

## Directory Details

### `/apps` - Applications

User-facing applications that demonstrate the platform capabilities.

```
apps/
└── demo-app/
    ├── backend/       # FastAPI demo service
    │   ├── app/       # Application code
    │   ├── tests/     # Backend tests
    │   └── Dockerfile
    ├── frontend/      # Next.js demo UI
    │   ├── src/       # Frontend code
    │   ├── tests/     # Frontend tests
    │   └── Dockerfile
    └── README.md      # Application documentation
```

**Purpose:** Provide realistic workloads that generate telemetry for the AI-native platform to analyze.

### `/services` - Backend Services

Core platform services and AI agents.

```
services/
├── api/               # Main platform API (future)
├── incident_agent/    # Incident analysis agent
│   ├── analyzer.py    # LLM-based analysis
│   ├── evidence.py    # Evidence retrieval
│   └── correlation.py # Root cause correlation
├── anomaly_agent/     # Anomaly detection
│   └── detector.py    # Statistical anomaly detection
├── remediation_agent/ # Remediation proposals
│   ├── proposal.py    # Proposal generation
│   └── policy.py      # Policy enforcement
├── incident_api/      # Incident lifecycle API
├── approval_api/      # Human approval workflow
├── cost_agent/        # Cost optimization (stub)
└── worker/            # Background job processor (future)
```

**Naming:** Services use Python snake_case to align with the platform's primary language.

### `/packages` - Shared Code

Reusable libraries consumed by multiple services.

```
packages/
├── contracts/         # Versioned data schemas
│   ├── incidents.py
│   ├── evidence.py
│   ├── remediation.py
│   ├── approvals.py
│   ├── audit.py
│   └── common.py
├── observability/     # Telemetry helpers
│   ├── otel.py
│   ├── logging.py
│   └── metrics.py
├── github_client/     # GitHub API adapter
├── kubernetes_client/ # Kubernetes API adapter (future)
├── llm/              # LLM provider abstraction
├── policy/           # Policy evaluation engine
└── test_fixtures/    # Shared test data
```

**Design:** Packages define interfaces, not implementations. Concrete implementations live in services.

### `/infra` - Infrastructure as Code

All infrastructure definitions and policies.

```
infra/
├── terraform/
│   ├── modules/           # Reusable Terraform modules
│   │   ├── kubernetes/
│   │   ├── postgresql/
│   │   ├── redis/
│   │   ├── container_registry/
│   │   ├── monitoring/
│   │   └── networking/
│   ├── environments/      # Environment-specific configs
│   │   ├── dev/
│   │   ├── staging/
│   │   └── production/
│   ├── tests/            # Terraform tests
│   ├── main.tf
│   ├── variables.tf
│   ├── versions.tf
│   └── .terraform.lock.hcl
└── kubernetes/
    ├── base/             # Base Kubernetes manifests
    │   ├── namespace.yaml
    │   ├── demo-api-deployment.yaml
    │   ├── demo-web-deployment.yaml
    │   ├── networkpolicies.yaml
    │   ├── serviceaccounts.yaml
    │   ├── autoscalers.yaml
    │   └── poddisruptionbudgets.yaml
    ├── overlays/         # Environment overlays
    │   ├── development/
    │   ├── staging/
    │   └── production/
    ├── policies/         # Policy definitions
    └── tests/           # Kubernetes manifest tests
```

**Principle:** Base manifests work in any environment; overlays provide environment-specific configuration.

### `/observability` - Telemetry Configuration

All monitoring, alerting, and observability definitions.

```
observability/
├── otel/
│   └── otel-collector-config.yaml  # OpenTelemetry Collector
├── prometheus/
│   └── prometheus.yml              # Scrape configs, recording rules
├── alerts/
│   └── alert-rules.yml             # Prometheus alert rules
└── dashboards/
    ├── demo-api-overview.json      # Application dashboard
    ├── kubernetes-health.json      # (future)
    ├── sre-slo.json                # (future)
    └── ai-agent-operations.json    # (future)
```

**Deployment:** These configs are deployed as ConfigMaps/files into the observability namespace.

### `/tests` - Cross-Cutting Tests

Tests that span multiple services or require special infrastructure.

```
tests/
├── contract/          # Contract tests (API schemas, interfaces)
├── integration/       # Integration tests (services + real dependencies)
├── e2e/              # End-to-end tests (full platform scenarios)
├── chaos/            # Chaos engineering tests
└── fixtures/         # Shared test fixtures
```

**Philosophy:** Unit tests live with the code they test. Integration/e2e tests live here because they cross boundaries.

### `/docs` - Documentation

All platform documentation.

```
docs/
├── 00-overview.md
├── 01-architecture.md
├── 02-repository-structure.md    # This file
├── 03-local-development.md
├── 04-configuration.md
├── 05-api.md                     # (future)
├── 06-data-model.md              # (future)
├── 07-observability.md           # (future)
├── 08-ai-agents.md
├── 09-incident-lifecycle.md
├── 10-security.md                # (future)
├── 11-threat-model.md            # (future)
├── 12-kubernetes.md              # (future)
├── 13-terraform.md               # (future)
├── 14-ci-cd.md                   # (future)
├── 15-testing-strategy.md        # (future)
├── 16-sre-slos.md
├── 17-cost-optimization.md       # (future)
├── 18-governance.md
├── 19-disaster-recovery.md       # (future)
├── 20-runbooks/                  # (future)
├── adr/                          # Architecture Decision Records
└── diagrams/                     # Architecture diagrams
```

**Numbering:** Documents are numbered for reading order, not strict hierarchy.

### `/scripts` - Automation

Development and operations automation scripts.

```
scripts/
├── setup/            # Setup and bootstrapping
├── deploy/           # Deployment helpers
├── test/             # Test execution helpers
├── slo_reporting/    # (future) SLO reports
└── incident/         # (future) Incident management tools
```

### `/migrations` - Database Migrations

Versioned database schema changes.

```
migrations/
├── 001_initial_schema.sql
├── 002_add_incident_tables.sql
└── ...
```

**Tool:** Migrations use a simple versioning scheme; future may adopt Alembic or Flyway.

### `/.github` - GitHub Configuration

GitHub-specific configuration and workflows.

```
.github/
├── workflows/        # GitHub Actions CI/CD
│   ├── ci.yml
│   ├── security.yml
│   ├── infrastructure.yml
│   └── repo-policy.yml
├── ISSUE_TEMPLATE/   # Issue templates
├── CODEOWNERS        # Code ownership
├── dependabot.yml    # Dependency updates
└── pull_request_template.md
```

## File Naming Conventions

### Python
- **Modules:** `snake_case.py`
- **Classes:** `PascalCase`
- **Functions:** `snake_case`
- **Constants:** `UPPER_SNAKE_CASE`

### TypeScript
- **Files:** `kebab-case.ts` or `PascalCase.tsx` for components
- **Classes:** `PascalCase`
- **Functions:** `camelCase`
- **Constants:** `UPPER_SNAKE_CASE`

### Configuration Files
- YAML: `.yml` preferred over `.yaml`
- Environment: `.env.example` (never commit actual `.env`)
- Lock files: Always committed

## Import Paths

Services import packages using absolute imports:

```python
from packages.contracts.incidents import Incident
from packages.observability.otel import init_telemetry
from packages.github_client.adapter import GitHubAdapter
```

**Rationale:** Absolute imports are more maintainable than relative imports in a monorepo.

## Configuration Files Location

### Root-Level Configuration

```
.editorconfig         # Editor settings
.gitignore           # Git ignore rules
.gitattributes       # Git line ending rules
.pre-commit-config.yaml  # Pre-commit hooks
.prettierrc.json     # Prettier formatting
.prettierignore      # Prettier ignore rules
pyproject.toml       # Python project metadata
uv.lock              # Python dependency lock
package.json         # Node.js dependencies
package-lock.json    # Node.js dependency lock
go.mod               # Go module (if/when Go components added)
Makefile            # Common commands
compose.yaml        # Local development services
compose.test.yaml   # Test environment services
Dockerfile          # (future) Multi-service image
```

### Language-Specific Configuration

```
.golangci.yml        # Go linter config
.mypy_cache/         # MyPy type checker cache
.ruff_cache/         # Ruff linter cache
.pytest_cache/       # Pytest cache
```

## State and Generated Files (Not Committed)

```
.venv/               # Python virtual environment
node_modules/        # Node.js dependencies
.next/               # Next.js build output
dist/                # Build artifacts
.coverage            # Test coverage data
.terraform/          # Terraform working directory
*.tfstate            # Terraform state (NEVER commit)
*.log                # Log files
.DS_Store            # macOS metadata
```

## Size Guidelines

- **Small files preferred:** < 500 lines for source files
- **Large modules:** Split into multiple files
- **Configuration:** One concern per file
- **Documentation:** One topic per file

## Adding New Components

### New Service

1. Create `services/new_service/`
2. Add `__init__.py` for Python package
3. Add `tests/` subdirectory
4. Add `README.md` with purpose and API
5. Update this document
6. Add CI validation

### New Package

1. Create `packages/new_package/`
2. Define interfaces/contracts only
3. Add comprehensive tests
4. Document public API
5. Version the package if it defines contracts

### New Infrastructure Module

1. Create `infra/terraform/modules/new_module/`
2. Add `main.tf`, `variables.tf`, `outputs.tf`
3. Add `README.md` with usage examples
4. Add tests in `infra/terraform/tests/`
5. Use the module in an environment

## Repository Metadata Files

### Required in Root

- **README.md:** Project overview, quick start
- **LICENSE:** Apache 2.0 (or chosen license)
- **CONTRIBUTING.md:** Contribution guidelines
- **CODE_OF_CONDUCT.md:** Community standards
- **SECURITY.md:** Security policy and vulnerability reporting
- **CHANGELOG.md:** Release notes

### Required in Subdirectories

- **README.md:** Purpose and usage for each major directory

## References

- [03-local-development.md](./03-local-development.md) - Setup instructions
- [04-configuration.md](./04-configuration.md) - Configuration management
- [Architecture Decision Records](./adr/README.md) - Monorepo decision rationale
