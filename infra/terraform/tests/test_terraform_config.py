"""Static validation of the Terraform configuration.

These checks run in the fast tier without a Terraform binary, cloud credentials or network access: they read
the `.tf` sources as text and assert the properties a reviewer would otherwise have to remember, most
importantly that no module or environment root embeds a secret value.

Schema and provider validation is a different job: `terraform fmt`, `init -backend=false`, `validate`, the
provider lock check and the Trivy configuration scan run in the `infrastructure.yml` workflow, because they need
the Terraform binary and the committed provider lockfile.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Final

import pytest

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
TERRAFORM_DIR: Final[Path] = REPO_ROOT / "infra" / "terraform"

#: Patterns that would mean a literal credential is committed in a `.tf` file.
FORBIDDEN_SECRET_PATTERNS: Final[tuple[tuple[str, str], ...]] = (
    (r'password\s*=\s*"[^"]+"', "literal password"),
    (r'secret\s*=\s*"[^"]+"', "literal secret"),
    (r'auth_token\s*=\s*"[^"]+"', "literal auth token"),
    (r'access_key\s*=\s*"[^"]+"', "literal access key"),
)

TF_FILES: Final[tuple[Path, ...]] = tuple(
    sorted(path for path in TERRAFORM_DIR.rglob("*.tf") if ".terraform" not in path.parts)
)
TF_FILE_IDS: Final[list[str]] = [str(path.relative_to(TERRAFORM_DIR)) for path in TF_FILES]


def _leading_comment(path: Path) -> str:
    """Return the first comment line of a `.tf` file, or an empty string."""
    # `utf-8-sig` transparently strips a leading BOM, which some editors inject
    # on Windows and which would otherwise hide the documentation comment.
    text = path.read_text(encoding="utf-8-sig")
    match = re.match(r"^\s*#[^\n]*", text)
    return match.group(0).strip() if match else ""


def test_terraform_sources_are_discovered() -> None:
    """A silently empty discovery set would make every parametrised check below vacuous."""
    assert TF_FILES, f"no .tf files found under {TERRAFORM_DIR}"
    assert TERRAFORM_DIR.joinpath(".terraform.lock.hcl").is_file(), (
        "the provider lockfile must be committed so provider resolution is reproducible"
    )


@pytest.mark.parametrize("path", TF_FILES, ids=TF_FILE_IDS)
def test_terraform_file_documents_its_responsibility(path: Path) -> None:
    """A file whose first line says what it does is reviewable without opening the rest."""
    assert _leading_comment(path), (
        f"{path.relative_to(TERRAFORM_DIR)} has no leading documentation comment"
    )


@pytest.mark.parametrize("path", TF_FILES, ids=TF_FILE_IDS)
def test_terraform_file_contains_no_literal_secret(path: Path) -> None:
    """Secrets arrive as variables from a secret manager, never as values in the repository."""
    text = path.read_text(encoding="utf-8")
    violations = [label for pattern, label in FORBIDDEN_SECRET_PATTERNS if re.search(pattern, text)]
    assert not violations, f"{path.relative_to(TERRAFORM_DIR)} contains: {', '.join(violations)}"


def test_provider_constraints_are_declared() -> None:
    """Terraform and every provider are pinned, so a plan is reproducible."""
    version_files = [path for path in TF_FILES if path.name == "versions.tf"]
    assert version_files, "no versions.tf declares provider constraints"
    for path in version_files:
        text = path.read_text(encoding="utf-8")
        assert "required_version" in text, (
            f"{path.relative_to(TERRAFORM_DIR)} declares no Terraform version constraint"
        )
        assert "required_providers" in text, (
            f"{path.relative_to(TERRAFORM_DIR)} declares no provider version constraint"
        )


def test_module_sources_are_local_and_versioned_by_path() -> None:
    """A module call that names a local path is reviewable; a floating registry version is not.

    Only `module` blocks are inspected -- `required_providers` sources such as
    `hashicorp/aws` are pinned by the committed `.terraform.lock.hcl` and are not
    module calls.
    """
    module_calls = [
        (path, match.group(1))
        for path in TF_FILES
        for match in re.finditer(
            r'module\s+"[^"]+"\s*\{[^}]*source\s*=\s*"([^"]+)"',
            path.read_text(encoding="utf-8"),
        )
    ]
    assert module_calls, "no module sources were found; module reuse is the point of the layout"
    for path, source in module_calls:
        assert source.startswith(("./", "../")) or source.startswith("git::"), (
            f"{path.relative_to(TERRAFORM_DIR)} uses an unpinned module source: {source}"
        )


ENVIRONMENTS: Final[tuple[str, ...]] = ("dev", "staging", "production")


def test_environment_backends_use_encrypted_remote_state() -> None:
    """State must live in an encrypted remote backend, never on a local disk.

    Each environment root declares an S3 backend with `encrypt = true` plus a
    bucket, key, region and DynamoDB lock table, so concurrent runs cannot
    corrupt state and no `*.tfstate` is ever committed (the repo policy check
    fails the build on any tracked state file).
    """
    for env in ENVIRONMENTS:
        backend = TERRAFORM_DIR / "environments" / env / "backend.tf"
        assert backend.is_file(), f"environments/{env}/backend.tf is missing"
        text = backend.read_text(encoding="utf-8")
        assert re.search(r'backend\s+"s3"', text), (
            f"environments/{env}/backend.tf does not declare an S3 remote backend"
        )
        for token in ("bucket", "key", "region", "dynamodb_table", "encrypt"):
            assert token in text, f"environments/{env}/backend.tf does not configure {token!r}"
        assert re.search(r"encrypt\s*=\s*true", text), (
            f"environments/{env}/backend.tf must enable backend encryption"
        )


def test_infrastructure_workflow_gates_terraform_policy() -> None:
    """The infrastructure workflow must gate every environment root on fmt, validate and policy scans.

    This keeps the README Phase 4 claim honest: scanning and remote-state drift
    cannot regress silently when the workflow is the enforcement point.
    """
    workflow = REPO_ROOT / ".github" / "workflows" / "infrastructure.yml"
    assert workflow.is_file(), ".github/workflows/infrastructure.yml is missing"
    text = workflow.read_text(encoding="utf-8")
    assert "terraform fmt -check -recursive" in text, (
        "infrastructure.yml must run `terraform fmt -check -recursive`"
    )
    assert "environments/*" in text, (
        "infrastructure.yml must iterate over infra/terraform/environments/*"
    )
    assert "terraform validate" in text, (
        "infrastructure.yml must run `terraform validate` per environment root"
    )
    assert "bridgecrewio/checkov-action" in text, (
        "infrastructure.yml must run a Checkov policy scan"
    )
    assert "soft_fail: false" in text, "infrastructure.yml must fail the build on Checkov findings"
    assert "aquasecurity/tfsec-action" in text, "infrastructure.yml must run a tfsec policy scan"
    assert "--minimum-severity HIGH" in text, (
        "infrastructure.yml must fail the build on HIGH-severity tfsec findings"
    )
    assert "aquasecurity/trivy-action" in text, "infrastructure.yml must run a Trivy IaC scan"


def test_terraform_strategy_is_documented() -> None:
    """docs/13-terraform.md must exist and describe the backend and CI gates above."""
    doc = REPO_ROOT / "docs" / "13-terraform.md"
    assert doc.is_file(), "docs/13-terraform.md is missing"
    text = doc.read_text(encoding="utf-8")
    for token in (
        "backend.tf",
        "encrypt",
        "dynamodb_table",
        "tfsec",
        "Checkov",
        "infrastructure.yml",
    ):
        assert token in text, f"docs/13-terraform.md does not document {token!r}"
