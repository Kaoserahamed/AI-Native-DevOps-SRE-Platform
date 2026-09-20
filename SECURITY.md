# Security Policy

This repository is a reference implementation of an AI-native DevOps/SRE platform. Security of the
control loop — agents, approvals, credentials and telemetry handling — is part of the product surface,
so security reports are treated as first-class bugs.

## Supported versions

Security fixes are applied to the latest release on `main`. Older tags are not maintained.

| Version | Supported |
| --- | --- |
| Latest release / `main` | Yes |
| Older tags | No |

## Reporting a vulnerability

**Do not open a public issue for a security problem.**

Report privately using GitHub's [private vulnerability reporting](https://docs.github.com/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository (Security → Report a vulnerability), or by email to **akaoser41@gmail.com**.

Please include:

- affected component (API, agent, adapter, manifest, Terraform module, workflow) and commit/tag;
- a description of the issue and its security impact;
- reproduction steps or a proof of concept, and any relevant logs with secrets redacted;
- whether the issue is already public, and any suggested remediation.

Expect an acknowledgement within **3 business days** and an initial assessment within **10 business
days**. We will agree a disclosure timeline with you; coordinated disclosure after a fix ships is
preferred, and we will credit reporters who want acknowledgement.

## Scope

In scope:

- The platform API, agent runtime, evidence retrieval, policy engine, approval workflow and audit trail.
- Adapters that talk to GitHub, Kubernetes, Prometheus, PostgreSQL, Redis and LLM providers.
- CI/CD workflows, container images, Kubernetes manifests, Terraform modules and repository governance.
- Secrets handling, least privilege and prompt-injection defences for untrusted telemetry.

Out of scope:

- The intentional failure mode in the demo application. It is a fixture that exists so incident
  scenarios can be reproduced and is enabled only behind a test-only configuration flag. Report it only
  if it can be activated in a non-test environment or without the documented flag (see
  `docs/10-security.md` once the security documentation lands).
- Vulnerabilities that require an attacker to already hold repository write access or cluster admin.
- Findings produced only by automated scanners without a demonstrated security impact.

## Safe harbour

We consider security research conducted in good faith to be authorized, and we will not pursue legal
action for it, provided you avoid privacy violations, service disruption, data destruction and any
interaction with accounts or data you do not own. Use your own environment and credentials.

## Security expectations for contributors

- Never commit secrets, credentials, tokens, `.env` files, Terraform state, kubeconfigs or production data.
- Agents are read-only by default and may never mutate production without an explicit, auditable human approval.
- Telemetry, logs and GitHub content are untrusted input. They must never be able to redefine agent
  instructions, tool allowlists or policy.
- New privileged capabilities require a threat-model update and an ADR describing the trust boundary.

The threat model and security controls are delivered with the security phases of the implementation
backlog (`docs/10-security.md`, `docs/11-threat-model.md`) and are linked from this policy once published.
