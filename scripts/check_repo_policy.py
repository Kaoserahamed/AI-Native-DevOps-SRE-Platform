"""Validate repository governance policy.

This script is intentionally dependency-free (standard library only) so it can run on a fresh CI
runner before any dependency install, and on any developer machine that has Python 3.11+.

Checks performed:

1. every required governance file exists;
2. no forbidden artifact is tracked by git (secrets, Terraform state/plan, kubeconfigs, private keys,
   downloaded providers, generated scan output);
3. third-party GitHub Actions are pinned to a full 40-character commit SHA;
4. relative links in Markdown documents resolve to files that exist;
5. ``.github/CODEOWNERS`` declares a default catch-all rule.

Usage:
    python scripts/check_repo_policy.py [--root PATH] [--quiet]

Exit codes:
    0   every check passed
    1   at least one violation was found
    2   the script could not run (for example git is unavailable)
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import re
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES: tuple[str, ...] = (
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "CHANGELOG.md",
    ".gitattributes",
    ".gitignore",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/incident.yml",
    ".github/ISSUE_TEMPLATE/security.yml",
    ".github/ISSUE_TEMPLATE/architecture_decision.yml",
    "docs/18-governance.md",
)

FORBIDDEN_TRACKED: tuple[tuple[str, str], ...] = (
    (r"(^|/)\.env$", "environment file that carries secrets"),
    (r"(^|/)\.env\.(?!example$)[^/]+$", "environment file variant"),
    (r"\.tfstate(\.|$)", "Terraform state (must live in a remote backend)"),
    (r"\.tfplan(\.json)?$", "Terraform plan"),
    (r"(^|/)kubeconfig[^/]*$", "cluster credentials"),
    (r"(^|/)\.terraform/", "downloaded Terraform providers"),
    (r"\.(pem|p12|pfx|jks)$", "private key material"),
    (r"(^|/)id_(rsa|dsa|ecdsa|ed25519)$", "SSH private key"),
    (r"secrets?\.(ya?ml|json|env)$", "plaintext secret manifest"),
)

MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
WORKFLOW_USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)\s*(?:#.*)?$")
FULL_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
CODEOWNERS_DEFAULT_RULE = re.compile(r"^\*\s+\S+", re.MULTILINE)
CODEOWNERS_COMMENT = re.compile(r"(^|\s)#.*$")
EXTERNAL_LINK_PREFIXES = ("http://", "https://", "mailto:", "tel:", "ftp://")


def relative_links(markdown_path: Path) -> list[str]:
    """Return the non-external link targets found in one Markdown file."""
    targets: list[str] = []
    for match in MARKDOWN_LINK.finditer(markdown_path.read_text(encoding="utf-8")):
        target = match.group(1).strip()
        if target.startswith(EXTERNAL_LINK_PREFIXES) or target.startswith("#"):
            continue
        if any(token in target for token in ("<", ">", "{", "}")):
            continue  # template or placeholder, not a real link
        targets.append(target)
    return targets


def resolve_link(root: Path, markdown_path: Path, target: str) -> Path | None:
    """Resolve a Markdown link target to a path, or return None when it cannot be resolved."""
    clean = target.split("#", 1)[0].split("?", 1)[0]
    if not clean:
        return None
    base = root if clean.startswith("/") else markdown_path.parent
    return (base / clean.lstrip("/")).resolve()


def check_required_files(root: Path) -> list[str]:
    """Return violations for missing governance files."""
    return [
        f"missing required governance file: {name}"
        for name in REQUIRED_FILES
        if not (root / name).is_file()
    ]


def tracked_files(root: Path) -> list[str]:
    """Return the files tracked by git, raising RuntimeError when git cannot be used."""
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:  # pragma: no cover
        raise RuntimeError(f"unable to list tracked files with git: {error}") from error
    return [path for path in completed.stdout.split("\0") if path]


def check_forbidden_tracked_files(root: Path) -> list[str]:
    """Return violations for forbidden artifact types that are tracked by git."""
    violations: list[str] = []
    for path in tracked_files(root):
        for pattern, reason in FORBIDDEN_TRACKED:
            if re.search(pattern, path):
                violations.append(f"forbidden tracked file ({reason}): {path}")
    return violations


def check_workflow_actions_pinned(root: Path) -> list[str]:
    """Return violations for workflow actions that are not pinned to a full commit SHA."""
    violations: list[str] = []
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return violations
    for workflow in sorted(workflows_dir.glob("*.y*ml")):
        lines = workflow.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            match = WORKFLOW_USES.match(line)
            if match is None:
                continue
            reference = match.group(1)
            if reference.startswith(("./", "docker://")):
                continue
            _, _, version = reference.partition("@")
            if not version or FULL_COMMIT_SHA.match(version) is None:
                violations.append(
                    f"{workflow.relative_to(root)}:{number} is not pinned to a commit SHA: {reference}"
                )
    return violations


def check_markdown_links(root: Path) -> list[str]:
    """Return violations for relative Markdown links that do not resolve to an existing path."""
    # Directories that hold downloaded or generated content rather than repository documentation:
    # `node_modules` (and the Python virtual environment) are dependency trees, and `.tools` holds
    # checksum-verified tool binaries fetched by the validation scripts, which ship their own README.
    skip_dirs = {".git", ".venv", ".tools", "node_modules"}
    violations: list[str] = []
    for document in sorted(root.rglob("*.md")):
        if any(part in skip_dirs for part in document.parts):
            continue
        for target in relative_links(document):
            resolved = resolve_link(root, document, target)
            if resolved is not None and not resolved.exists():
                violations.append(f"{document.relative_to(root)} links to missing path: {target}")
    return violations


def check_codeowners_default_rule(root: Path) -> list[str]:
    """Return violations for a CODEOWNERS file without a default catch-all rule."""
    codeowners = root / ".github" / "CODEOWNERS"
    if not codeowners.is_file():
        return ["missing .github/CODEOWNERS"]
    text = CODEOWNERS_COMMENT.sub("", codeowners.read_text(encoding="utf-8"))
    if CODEOWNERS_DEFAULT_RULE.search(text) is None:
        return [".github/CODEOWNERS has no default catch-all rule (`* @owner`)"]
    return []


CHECKS = (
    ("required governance files", check_required_files),
    ("forbidden tracked files", check_forbidden_tracked_files),
    ("pinned workflow actions", check_workflow_actions_pinned),
    ("markdown links", check_markdown_links),
    ("CODEOWNERS default rule", check_codeowners_default_rule),
)


def run_checks(root: Path, quiet: bool = False) -> list[str]:
    """Run every check against ``root`` and return all violations."""
    violations: list[str] = []
    for name, check in CHECKS:
        found = check(root)
        violations.extend(found)
        if not quiet:
            print(f"[{'FAIL' if found else 'PASS'}] {name}")
            for item in found:
                print(f"         - {item}")
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point used by CI and by local runs."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root to validate")
    parser.add_argument("--quiet", action="store_true", help="print violations only")
    args = parser.parse_args(argv)

    try:
        violations = run_checks(args.root.resolve(), quiet=args.quiet)
    except RuntimeError as error:
        print(f"repository policy check could not run: {error}", file=sys.stderr)
        return 2

    if violations:
        print(f"repository policy check failed with {len(violations)} violation(s)")
        return 1
    print("repository policy check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
