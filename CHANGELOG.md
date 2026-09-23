# Changelog

All notable changes to the AI-Native DevOps & SRE Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive CI/CD workflows with lint, typecheck, test, integration, and security scanning
- Docker Compose configuration for local development infrastructure
- Anomaly detection service with statistical analysis and baseline tracking
- Root cause correlation engine for incident analysis
- Complete incident lifecycle state machine API
- Enhanced approval workflow with expiration and audit trail
- Centralized structured logging with Sentry integration
- Comprehensive test suite with 38+ unit tests for core services
- Container build workflow with Trivy scanning and SBOM generation
- Enhanced `.env.example` with all configuration variables
- OpenTelemetry instrumentation for traces, metrics, and logs
- Prometheus alert rules for SRE monitoring
- Grafana dashboard for API overview
- Complete documentation structure
- Terraform `fmt`/`validate`/`plan` and Checkov/tfsec policy gating in `infrastructure.yml`, with per-environment encrypted remote state backends
- Sentry error tracking resolved from `SENTRY_DSN`/`SENTRY_ENVIRONMENT` inside `configure_logging`

### Changed
- Improved README with clearer quick start instructions
- Enhanced security scanning with pip-audit, npm audit, Bandit, and Semgrep
- Updated observability configuration for production readiness

### Fixed
- Missing environment variables in `.env.example`
- Documentation gaps in repository structure and setup guides

## [0.1.0] - 2026-09-21

### Added
- Initial platform foundation with repository governance
- Demo application (FastAPI backend + Next.js frontend)
- Kubernetes base manifests and environment overlays
- Terraform infrastructure modules (6 reusable modules)
- Network policies and Pod Security Standards
- GitHub adapter for issue and PR automation
- LLM provider abstraction with retry and fallback
- Remediation proposal engine with policy controls
- Versioned data contracts for incidents, evidence, and approvals
- Architecture documentation and ADRs
- OpenTelemetry Collector configuration
- PostgreSQL and Redis integration
- Pre-commit hooks and code quality tooling

### Security
- Secret scanning with TruffleHog
- Dependency vulnerability scanning configured
- No secrets or credentials committed
- Pod Security Standards enforcement (restricted profile)
- Network segmentation with default-deny policies

## Release Guidelines

### Version Numbering

- **Major** (x.0.0): Breaking changes, architecture changes
- **Minor** (0.x.0): New features, backward compatible
- **Patch** (0.0.x): Bug fixes, security patches

### Release Process

1. Update CHANGELOG.md with release notes
2. Update version in `pyproject.toml` and `package.json`
3. Create git tag: `git tag -a v0.1.0 -m "Release v0.1.0"`
4. Push tag: `git push origin v0.1.0`
5. GitHub Actions will build and publish artifacts

### Migration Notes

When upgrading between versions, check:
- Database migrations in `migrations/`
- Environment variable changes in `.env.example`
- Breaking API changes in release notes
- Kubernetes manifest updates in `infra/kubernetes/`

## Links

- [Repository](https://github.com/Kaoserahamed/AI-Native-DevOps-SRE-Platform)
- [Documentation](docs/)
- [Contributing Guide](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
