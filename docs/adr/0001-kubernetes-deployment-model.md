# ADR-0001: Deploy Kubernetes workloads with a Kustomize base and environment overlays

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** Platform maintainer
- **Related:** `docs/12-kubernetes.md`, `.github/workflows/k8s.yml`, phase 3 of the implementation backlog

## Context

The platform and the demo workload both run on Kubernetes. Manifests must be reviewable in pull
requests, validated before merge, and must differ between development, staging and production only in
ways that are explicitly visible (replica counts, resources, observability settings, policy settings).
Configuration mistakes here are the most common cause of production incidents in this repository's
architecture, and the AI agents propose changes to exactly these manifests.

## Decision

We will keep a single Kustomize **base** per workload in `infra/kubernetes/base/` and per-environment
**overlays** in `infra/kubernetes/overlays/{development,staging,production}/`. Overlays may only change
what the environment legitimately differs in: replica counts, resource sizing, environment-specific
configuration, observability sampling, and policy settings. Every manifest is validated with
kubeconform (schema), kube-linter (best practice) and the policy checks in CI before merge, and images
are referenced by immutable digest in the production overlay.

## Alternatives considered

| Alternative | Why it was rejected |
| --- | --- |
| Helm charts | A templating language in the deployment path adds failure modes and makes the rendered result harder to review; the repository has no need for packaging or release indirection |
| One manifest directory per environment | Massive duplication: a fix must be applied three times and drift is invisible |
| Terraform Kubernetes provider | Deployment state does not belong in the infrastructure state file; rollbacks and GitOps review are worse |
| GitOps controller (Argo CD/Flux) | Out of scope for a reference implementation; the pipeline performs the apply step and the repository stays the single source of truth |

## Consequences

- **Positive:** rendered manifests are readable, `kustomize build` output is diffable in review, and
  environment differences are explicit and small.
- **Negative:** overlays can drift from the base (mitigated by validation and by deploying every overlay
  in e2e tests); no packaging/release abstraction for reuse outside this repository.
- **Neutral:** the production overlay is owned by a code owner, and any change to it requires review.

## Security, privacy and agent impact

No new trust boundary is created; TB-5 (control plane → Kubernetes workload) is strengthened because
deny-by-default policies, resource allowlists and image reference validation become CI gates. Agent
proposals must target the same manifest paths, so the policy engine can evaluate proposed changes against
the same allowlists.

## Validation

- `k8s.yml` renders every overlay, then runs kubeconform, kube-linter, policy validation and image
  reference checks.
- The ephemeral-cluster e2e job deploys the development overlay and runs smoke tests, so a broken overlay
  fails CI rather than production.
- Production only ever receives images referenced by digest, and rollback is a re-apply of the previous
  overlay revision.
