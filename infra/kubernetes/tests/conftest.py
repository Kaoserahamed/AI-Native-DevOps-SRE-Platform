"""Shared fixtures for the Kubernetes manifest policy tests.

These tests read the manifest **sources**, not a rendered output: they run in the fast tier, need no
cluster and no cluster tooling, and they fail when a manifest stops meeting the platform's policy. Rendered
manifests are validated separately by kubeconform (schema) and kube-linter (best practice) in the `k8s.yml`
job — see `docs/12-kubernetes.md`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

import pytest
import yaml

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
KUBERNETES_DIR: Final[Path] = REPO_ROOT / "infra" / "kubernetes"
BASE_DIR: Final[Path] = KUBERNETES_DIR / "base"
OVERLAYS_DIR: Final[Path] = KUBERNETES_DIR / "overlays"

#: Namespace every demo workload object lives in. It matches `ServiceRef.namespace` in the platform
#: contracts, so an alert, its evidence and the objects it names all use one identifier.
NAMESPACE: Final[str] = "demo"

#: Labels every manifest in the base must carry, so ownership and tooling are never in doubt.
STANDARD_LABELS: Final[tuple[str, ...]] = (
    "app.kubernetes.io/part-of",
    "app.kubernetes.io/managed-by",
)

#: Ports the demo API may reach outside the cluster; a base egress rule without an address is only
#: acceptable for exactly these data-store ports.
DATA_STORE_PORTS: Final[frozenset[int]] = frozenset({5432, 6379})


@dataclass(frozen=True)
class Manifest:
    """One YAML document plus the file it came from."""

    path: Path
    document: dict[str, Any]

    @property
    def kind(self) -> str:
        return str(self.document.get("kind", ""))

    @property
    def name(self) -> str:
        metadata = self.document.get("metadata")
        if isinstance(metadata, dict):
            return str(metadata.get("name", ""))
        return ""

    @property
    def labels(self) -> dict[str, Any]:
        metadata = self.document.get("metadata")
        if isinstance(metadata, dict):
            labels = metadata.get("labels")
            if isinstance(labels, dict):
                return cast(dict[str, Any], labels)
        return {}

    @property
    def identifier(self) -> str:
        return f"{self.path.name}:{self.kind}/{self.name}"


def load_documents(path: Path) -> list[Manifest]:
    """Load every YAML document in one manifest file."""
    documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    return [
        Manifest(path=path, document=document) for document in documents if document is not None
    ]


def load_directory(directory: Path) -> list[Manifest]:
    """Load every manifest in a directory, skipping the kustomization index itself."""
    manifests: list[Manifest] = []
    for path in sorted(directory.glob("*.yaml")):
        if path.name == "kustomization.yaml":
            continue
        manifests.extend(load_documents(path))
    return manifests


def pod_spec(manifest: Manifest) -> dict[str, Any]:
    """Return the pod template spec of a workload manifest."""
    template = cast(dict[str, Any], manifest.document["spec"]["template"])
    return cast(dict[str, Any], template["spec"])


def containers(manifest: Manifest) -> list[dict[str, Any]]:
    """Return the containers of a workload manifest."""
    return [cast(dict[str, Any], entry) for entry in pod_spec(manifest).get("containers", [])]


def by_kind(manifests: Sequence[Manifest], kind: str) -> list[Manifest]:
    """Return every manifest of one kind."""
    return [manifest for manifest in manifests if manifest.kind == kind]


def find(manifests: Sequence[Manifest], kind: str, name: str) -> Manifest:
    """Return the single manifest matching a kind and name, failing loudly otherwise."""
    matches = [m for m in manifests if m.kind == kind and m.name == name]
    assert len(matches) == 1, f"expected exactly one {kind}/{name}, found {len(matches)}"
    return matches[0]


@pytest.fixture(scope="session")
def base_manifests() -> list[Manifest]:
    """Every manifest object defined in `infra/kubernetes/base`."""
    return load_directory(BASE_DIR)


@pytest.fixture(scope="session")
def workloads(base_manifests: list[Manifest]) -> list[Manifest]:
    """The workload (Deployment) manifests in the base."""
    return by_kind(base_manifests, "Deployment")


@pytest.fixture(scope="session")
def overlay_manifests() -> list[Manifest]:
    """Every manifest defined by an environment overlay."""
    manifests: list[Manifest] = []
    if OVERLAYS_DIR.is_dir():
        for directory in sorted(path for path in OVERLAYS_DIR.iterdir() if path.is_dir()):
            manifests.extend(load_directory(directory))
    return manifests
