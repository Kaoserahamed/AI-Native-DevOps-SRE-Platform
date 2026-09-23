"""Fast-tier policy tests for Kubernetes manifests.

These tests validate the raw `.yaml` sources in `infra/kubernetes`, not a
rendered cluster state. They run without a cluster, without cluster tooling,
and without network access, so they belong in the cheap verification gate
alongside formatting, linting, type-checking, unit tests and the terraform
configuration tests.

Rendered-output validation is a different job handled by `kubeconform` and
`kube-linter` inside the `k8s.yml` workflow.
"""
