# ADR-0009: Terraform with reusable modules and isolated environment state

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** Platform maintainer
- **Related:** `docs/13-terraform.md`, `infra/terraform/`, phase 4 of the implementation backlog

## Context

The platform needs reproducible infrastructure: a Kubernetes cluster, PostgreSQL, Redis, a container
registry and the networking and monitoring dependencies they require — in development, staging and
production. Environments must be isolated so that a mistake in one cannot affect another, provider and
module versions must be pinned so that plans are reproducible, state must never be committed, and the
agent-driven workflow must never be able to apply infrastructure changes without review.

## Decision

We will use Terraform with:

- **Reusable modules** in `infra/terraform/modules/` (cluster, PostgreSQL, Redis, registry, networking,
  monitoring dependencies) with documented inputs/outputs and explicit version interfaces.
- **Thin per-environment roots** in `infra/terraform/environments/{development,staging,production}/`, each
  with its own remote state backend (encrypted, versioned, locking enabled) and its own variable values.
- **Exact version pinning**: `required_version` for Terraform itself, exact provider and module versions,
  and a committed `.terraform.lock.hcl` per root.
- **Naming and tagging conventions** applied by modules so every resource is attributable to repository,
  environment, owner and cost centre.
- **CI validation only**: `terraform fmt -check`, `init -backend=false`, `validate`, lockfile drift
  detection and `trivy config`/`tflint` scans run on every pull request. `plan` may run read-only in a
  controlled job; `apply` runs only from a protected branch or an approved environment, never from a pull
  request, and production apply requires the production approval gate.

## Alternatives considered

| Alternative | Why it was rejected |
| --- | --- |
| Terragrunt | Adds a wrapper tool and its own conventions for a repository whose environment differences are small |
| Pulumi/CDK | General-purpose languages are attractive, but the ecosystem's review and policy-scanning tooling around Terraform is broader and the backlog assumes Terraform |
| Terraform workspaces for environments | A single state per root with workspace switching invites cross-environment mistakes and weakens isolation |
| Manual provisioning documented in a runbook | Not reproducible, not reviewable, and untestable in CI |
| Crossplane (Kubernetes-native infrastructure) | Interesting direction, but the platform already uses Kubernetes for workloads and would gain a second control plane to operate |

## Consequences

- **Positive:** environment isolation, reviewable plans, pinned providers, repeatable bootstrap, and
  infrastructure changes that flow through the same governance as code.
- **Negative:** duplicated root configuration and per-environment state backends to manage; state contains
  sensitive values, so the backend must be encrypted and access-controlled; provider lockfiles must be
  refreshed deliberately (never upgraded implicitly).
- **Neutral:** module interfaces become a compatibility contract: changing an input requires updating every
  environment root and its documentation in the same change.

## Security, privacy and agent impact

TB-5 and TB-6 are affected. Credentials for providers come from the pipeline's secret store, never from
the repository or from Terraform variables committed to git; state is remote and encrypted because it can
contain sensitive values; production apply requires an approved environment. Agents may read plan output
and propose infrastructure changes, but they cannot run `apply`: infrastructure mutation follows the same
policy and approval model as workload changes, and rollback is a re-apply of a previous revision rather
than an agent action.

## Validation

- CI runs `fmt -check`, `init -backend=false`, `validate`, provider lockfile verification and IaC scanning
  for every root in the repository.
- Module inputs/outputs are documented and validated with an example usage per module.
- A restore/recovery drill for the state backend is documented in the disaster-recovery documentation, and
  an infrastructure test asserts that a rendered plan for the development root is stable (no unexpected
  diff) when nothing changed.
