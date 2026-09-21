"""Structural expectations for the Kubernetes manifests.

A manifest that is well labelled, explicitly namespaced and listed in the kustomization index is one a
reviewer can find and a tool can attribute. These tests exist because every one of those properties has
broken a real deployment at some point: an unlisted file silently never applied, a missing namespace landed
the object in `default`, and an unlabelled object could not be selected by the autoscaler or the network
policy.
"""

from __future__ import annotations

from pathlib import Path

from infra.kubernetes.tests.conftest import (
    BASE_DIR,
    NAMESPACE,
    STANDARD_LABELS,
    Manifest,
)
import pytest
import yaml

pytestmark = pytest.mark.unit


def test_every_document_has_api_version_kind_and_name(base_manifests: list[Manifest]) -> None:
    """A manifest without an identity cannot be validated, selected or applied."""
    assert base_manifests, "no manifests were found in infra/kubernetes/base"

    for manifest in base_manifests:
        assert manifest.document.get("apiVersion"), f"{manifest.identifier} has no apiVersion"
        assert manifest.kind, f"{manifest.identifier} has no kind"
        assert manifest.name, f"{manifest.identifier} has no metadata.name"


def test_namespaced_objects_use_the_workload_namespace(base_manifests: list[Manifest]) -> None:
    """Objects that belong to a namespace must say so, and it must be the demo namespace."""
    for manifest in base_manifests:
        if manifest.kind == "Namespace":
            continue
        metadata = manifest.document["metadata"]
        assert metadata.get("namespace") == NAMESPACE, (
            f"{manifest.identifier} is not explicitly placed in the {NAMESPACE} namespace"
        )


def test_every_manifest_carries_the_standard_labels(base_manifests: list[Manifest]) -> None:
    """Ownership and tooling are attributes of the object, not of someone's memory."""
    for manifest in base_manifests:
        for label in STANDARD_LABELS:
            assert label in manifest.labels, f"{manifest.identifier} is missing the {label} label"


def test_base_kustomization_lists_every_manifest_file() -> None:
    """An unlisted file is a manifest that silently never applies."""
    kustomization = yaml.safe_load((BASE_DIR / "kustomization.yaml").read_text(encoding="utf-8"))
    resources = kustomization["resources"]

    # Separate top-level manifest files from subdirectory kustomization references
    top_level_names = set()
    subdirectory_kustomizations = set()

    for entry in resources:
        path = Path(entry)
        if path.suffix == ".yaml" and path.name == "kustomization.yaml" and path.parent != Path():
            # This is a reference to a subdirectory's kustomization file
            subdirectory_kustomizations.add(path.parent)
        else:
            top_level_names.add(path.name)

    # Check top-level .yaml files (excluding kustomization.yaml itself)
    top_level_files = {
        path.name for path in BASE_DIR.glob("*.yaml") if path.name != "kustomization.yaml"
    }
    assert top_level_files - top_level_names == set(), (
        f"top-level manifest files not referenced by kustomization.yaml: "
        f"{top_level_files - top_level_names}"
    )
    assert top_level_names - top_level_files == set(), (
        f"kustomization.yaml references top-level files that do not exist: "
        f"{top_level_names - top_level_files}"
    )

    # Check each subdirectory's kustomization
    for subdir in subdirectory_kustomizations:
        subdir_path = BASE_DIR / subdir
        assert subdir_path.is_dir(), f"subdirectory {subdir} does not exist"
        subdir_kustomization_file = subdir_path / "kustomization.yaml"
        assert subdir_kustomization_file.exists(), (
            f"subdirectory {subdir} has no kustomization.yaml"
        )
        subdir_kustomization = yaml.safe_load(subdir_kustomization_file.read_text(encoding="utf-8"))
        subdir_resources = {Path(entry).name for entry in subdir_kustomization["resources"]}
        subdir_files = {
            path.name for path in subdir_path.glob("*.yaml") if path.name != "kustomization.yaml"
        }
        assert subdir_files - subdir_resources == set(), (
            f"files in {subdir}/ not referenced by its kustomization.yaml: "
            f"{subdir_files - subdir_resources}"
        )
        assert subdir_resources - subdir_files == set(), (
            f"kustomization.yaml in {subdir}/ references files that do not exist: "
            f"{subdir_resources - subdir_files}"
        )


def test_workload_selectors_match_their_pod_labels(workloads: list[Manifest]) -> None:
    """A selector that does not match the pod template produces a Deployment that never becomes ready."""
    for workload in workloads:
        selector = workload.document["spec"]["selector"]["matchLabels"]
        template_labels = workload.document["spec"]["template"]["metadata"]["labels"]

        for key, value in selector.items():
            assert template_labels.get(key) == value, (
                f"{workload.identifier} selects {key}={value} but its pod template labels it "
                f"{template_labels.get(key)!r}"
            )


def test_selectors_do_not_depend_on_release_metadata(workloads: list[Manifest]) -> None:
    """Version or revision labels in a selector make the Deployment immutable between releases."""
    volatile = {"app.kubernetes.io/version", "app.kubernetes.io/revision", "helm.sh/chart"}

    for workload in workloads:
        selector = workload.document["spec"]["selector"]["matchLabels"]

        assert set(selector) & volatile == set(), (
            f"{workload.identifier} selects on release metadata, which cannot change"
        )
