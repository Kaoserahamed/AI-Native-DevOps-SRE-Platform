# ADR-0008: GitHub integration through a least-privilege adapter

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** Platform maintainer
- **Related:** `docs/14-ci-cd.md`, `packages/github_client/`, phase 10 of the implementation backlog

## Context

GitHub is the system of record for code, change review and deployment execution: the platform reads
deployment history and commit metadata as incident evidence, and it writes incident issues and
remediation pull requests. The credential it uses is therefore high value — a leaked token could read
private code, open pull requests, or tamper with pipelines. Every write must also be idempotent, because
retries are unavoidable.

## Decision

All GitHub access goes through a single adapter in `packages/github_client/`. It authenticates as a
**GitHub App installation** (short-lived, per-repository installation tokens) and falls back to a
fine-grained personal access token only for local development. The permission matrix is explicit and
minimal:

| Capability | Permission |
| --- | --- |
| Read repository metadata, commits, branches, tags | `contents: read` |
| Read deployment and environment history | `deployments: read` |
| Read check runs and commit statuses | `checks: read`, `statuses: read` |
| Open and update incident issues | `issues: write` |
| Create remediation branches, pull requests and comments | `contents: write` (scoped to the remediation branch), `pull-requests: write` |
| Not granted | `administration`, `workflows`, `secrets`, `packages`, `members`, `actions: write` |

The adapter provides rate-limit awareness, ETag caching for reads, bounded retries with jitter, structured
error mapping, and deterministic identifiers: remediation branches are named from the incident ID plus the
action hash, and every generated issue or pull request carries a marker comment with a machine-readable
metadata block (incident ID, action hash, evidence IDs, validation results). Duplicate detection is based
on those markers, so a retry updates instead of creating a second artifact. Production-changing pull
requests are never auto-merged, and the adapter has no merge capability at all.

## Alternatives considered

| Alternative | Why it was rejected |
| --- | --- |
| Classic PATs with broad scopes | Long-lived, over-privileged, and typically owned by a person rather than an app |
| Acting as a human user account | Blurs attribution between people and automation in the audit trail |
| Direct `git push` instead of pull requests | Removes review, checks and the audit trail that the platform exists to demonstrate |
| `GITHUB_TOKEN` from the current workflow for all calls | Scoped to a single workflow run; unusable for a long-running service |
| Ad-hoc `httpx` calls in each service | Duplicated retry, caching and error semantics, and an unauditable permission footprint |

## Consequences

- **Positive:** one credential path, one place to enforce least privilege, idempotent writes, and evidence
  retrieval that is rate-limit aware and cached.
- **Negative:** GitHub App installations require setup documentation, and the token exchange adds a
  failure mode that must be retried and monitored.
- **Neutral:** the permission matrix is documentation that CI checks against the code's requested scopes.

## Security, privacy and agent impact

TB-3 (GitHub → control plane) and TB-5's write path cross here. Tokens are never logged, never stored in
the database, and are read from the platform's secret store at runtime. Content fetched from GitHub
(issue bodies, commit messages, PR descriptions) is untrusted input: it is never allowed to change agent
instructions, tool allowlists or policy, and it is sanitized before it is rendered into prompts or
Markdown.

## Validation

- Adapter contract tests run against a mocked GitHub API covering pagination, rate limiting, retries,
  error mapping and duplicate detection.
- A permission-matrix test asserts the scopes requested by the app match this ADR, and the repository
  policy check keeps workflows SHA-pinned.
- The e2e demonstration asserts that an incident issue and a remediation pull request are created exactly
  once, with the linked metadata block and the incident ID.
