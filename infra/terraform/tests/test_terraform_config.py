"""Terraform configuration tests.

Static checks that run in the fast tier without a Terraform binary or cloud
credentials. They validate structure, naming, and policy that can be verified
from the source files alone.
"""

from __future__ import annotations

import json
import re
import pytest
from pathlib import Path
def _top_comments(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^\s*#[^\n]*\n", text)
    return m.group(0).strip() if m else ""


def _resource_lines(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    resources = []
    for i, line in enumerate(lines, start=1):
        m = re.match(r"^\s*resource\s+\"(\w+)\"\s+\"(\w+)\"", line)
        if m:
            resources.append((i, m.group(1), m.group(2)))
    return resources


@pytest.mark.parametrize(
    "path", sorted(_tf_files()), ids=lambda p: str(p.relative_to(TERRAFORM_DIR))
)
def test_terraform_files_have_module_level_documentation(path: Path) -> None:
    """Every .tf file should open with a comment explaining its responsibility."""
    assert _top_comments(path), (
        f"{path.relative_to(TERRAFORM_DIR)} has no leading documentation comment"
    )


@pytest.mark.parametrize(
    "path", sorted(_tf_files()), ids=lambda p: str(p.relative_to(TERRAFORM_DIR))
)
def test_terraform_files_do_not_contain_hardcoded_secrets(path: Path) -> None:
    """No .tf file may embed a secret value, even as an example."""
    text = path.read_text(encoding="utf-8")
    forbidden = [
        (r'password\s*=\s*"[^"]+"', "literal password"),
        (r'secret\s*=\s*"[^"]+"', "literal secret"),
        (r'auth_token\s*=\s*"[^"]+"', "literal auth token"),
    ]
    violations = [label for pattern, label in forbidden if re.search(pattern, text)]
    assert not violations, (
        f"{path.relative_to(TERRAFORM_DIR)} contains: {', '.join(violations)}"
    )

REPO_ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_DIR = REPO_ROOT / "infra" / "terraform"


def _tf_files():
    return sorted(
        p for p in TERRAFORM_DIR.rglob("*.tf")
        if "tfstate" not in p.name and not p.name.endswith(".lock.hcl")
    )