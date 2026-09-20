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

[Unreleased]: https://github.com/Kaoserahamed/AI-Native-DevOps-SRE-Platform/commits/main
