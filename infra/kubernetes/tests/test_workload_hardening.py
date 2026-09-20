"""Workload hardening and Pod Security Standards expectations.

These tests pin the security properties a workload that an AI agent may
remediate must satisfy: no privileged containers, no host namespaces,
read-only root filesystems, dropped capabilities, non-root execution, and
explicit RBAC that grants no Kubernetes API access to the demo workloads
(which do not need it). Each property is enforced by a manifest, not by
runtime configuration, so it survives a redeploy.
"""

from __future__ import annotations

from infra.kubernetes.tests.conftest import (
    Manifest,
    by_kind,
    containers,
)
import pytest

pytestmark = pytest.mark.unit


def test_workloads_run_as_non_root(workloads: list[Manifest]) -> None:
    """A container running as root can escalate within the node."""
    for workload in workloads:
        spec = workload.document["spec"]["template"]["spec"]
        assert spec.get("securityContext", {}).get("runAsNonRoot") is True, (
            f"{workload.identifier} does not enforce runAsNonRoot"
        )


def test_workloads_do_not_use_host_namespaces(workloads: list[Manifest]) -> None:
    """Host PID/IPC/network namespaces give a container host-level access."""
    forbidden = {"hostPID", "hostIPC", "hostNetwork"}
    for workload in workloads:
        spec = workload.document["spec"]["template"]["spec"]
        set_hosts = forbidden & set(spec)
        assert not set_hosts, f"{workload.identifier} uses host namespaces: {set_hosts}"


def test_containers_have_read_only_root_filesystem(workloads: list[Manifest]) -> None:
    """A writable root filesystem lets a compromise persist or tamper with the image."""
    for workload in workloads:
        for container in containers(workload):
            security = container.get("securityContext", {})
            assert security.get("readOnlyRootFilesystem") is True, (
                f"{workload.identifier}/{container['name']} has a writable root filesystem"
            )
            assert security.get("allowPrivilegeEscalation") is False, (
                f"{workload.identifier}/{container['name']} allows privilege escalation"
            )


def test_containers_drop_all_capabilities(workloads: list[Manifest]) -> None:
    """Dropping ALL capabilities removes capabilities the app does not request."""
    for workload in workloads:
        for container in containers(workload):
            capabilities = container.get("securityContext", {}).get("capabilities", {})
            assert capabilities.get("drop") == ["ALL"], (
                f"{workload.identifier}/{container['name']} does not drop ALL capabilities"
            )


def test_workloads_use_seccomp_runtime_default(workloads: list[Manifest]) -> None:
    """RuntimeDefault seccomp is the least-privilege default that still allows normal operation."""
    for workload in workloads:
        spec = workload.document["spec"]["template"]["spec"]
        seccomp = spec.get("securityContext", {}).get("seccompProfile", {})
        assert seccomp.get("type") == "RuntimeDefault", (
            f"{workload.identifier} does not use RuntimeDefault seccomp"
        )


def test_workloads_have_no_privileged_containers(workloads: list[Manifest]) -> None:
    """A privileged container has full host access and defeats every other control."""
    for workload in workloads:
        for container in containers(workload):
            security = container.get("securityContext", {})
            assert security.get("privileged") is not True, (
                f"{workload.identifier}/{container['name']} runs as privileged"
            )


def test_service_account_tokens_are_not_mounted(workloads: list[Manifest]) -> None:
    """The demo workloads do not call the Kubernetes API, so they do not need a token."""
    for workload in workloads:
        spec = workload.document["spec"]["template"]["spec"]
        assert spec.get("automountServiceAccountToken") is False, (
            f"{workload.identifier} mounts a service account token"
        )


def test_workloads_have_resource_limits(workloads: list[Manifest]) -> None:
    """Without limits a runaway container can starve its neighbours on the node."""
    for workload in workloads:
        for container in containers(workload):
            resources = container.get("resources", {})
            assert resources.get("limits", {}).get("cpu"), (
                f"{workload.identifier}/{container['name']} has no CPU limit"
            )
            assert resources.get("limits", {}).get("memory"), (
                f"{workload.identifier}/{container['name']} has no memory limit"
            )


def test_namespace_enforces_pod_security_standards(base_manifests: list[Manifest]) -> None:
    """The namespace must enforce restricted pod security admission."""
    namespaces = by_kind(base_manifests, "Namespace")
    assert len(namespaces) == 1
    labels = namespaces[0].labels
    assert labels.get("pod-security.kubernetes.io/enforce") == "restricted", (
        "the namespace does not enforce restricted pod security"
    )
