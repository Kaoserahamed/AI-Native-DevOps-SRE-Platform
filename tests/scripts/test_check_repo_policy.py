"""Unit tests for the repository governance checker ``scripts/check_repo_policy.py``.

These tests are deterministic and never touch the network: file-system checks run against ``tmp_path``
fixtures and the git-backed check is exercised with a stubbed subprocess result.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from scripts import check_repo_policy

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.unit


def write_file(root: Path, relative: str, content: str = "") -> Path:
    """Create ``relative`` inside ``root`` and return its path."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_repository_satisfies_its_own_policy() -> None:
    """The checked-in repository must pass every governance check."""
    assert check_repo_policy.run_checks(REPO_ROOT, quiet=True) == []


def test_required_files_reported_when_missing(tmp_path: Path) -> None:
    violations = check_repo_policy.check_required_files(tmp_path)

    assert len(violations) == len(check_repo_policy.REQUIRED_FILES)
    assert all(
        violation.startswith("missing required governance file:") for violation in violations
    )


def test_required_files_pass_when_all_present(tmp_path: Path) -> None:
    for name in check_repo_policy.REQUIRED_FILES:
        write_file(tmp_path, name)

    assert check_repo_policy.check_required_files(tmp_path) == []


@pytest.mark.parametrize(
    "tracked",
    [".env", "env/production.tfstate", "kubeconfig", "id_rsa", "certs/server.pem", "secrets.yaml"],
)
def test_forbidden_tracked_files_detected(
    tmp_path: Path, tracked: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_repo_policy, "tracked_files", lambda _root: [tracked, "src/app.py"])

    violations = check_repo_policy.check_forbidden_tracked_files(tmp_path)

    assert len(violations) == 1
    assert tracked in violations[0]


def test_env_example_and_lockfile_are_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        check_repo_policy,
        "tracked_files",
        lambda _root: [".env.example", "infra/terraform/.terraform.lock.hcl"],
    )

    assert check_repo_policy.check_forbidden_tracked_files(tmp_path) == []


def test_tracked_files_raises_when_git_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(
            returncode=128, cmd=["git"], stderr="not a git repository"
        )

    monkeypatch.setattr(subprocess, "run", failing_run)

    with pytest.raises(RuntimeError, match="unable to list tracked files"):
        check_repo_policy.tracked_files(tmp_path)


def test_tracked_files_parses_nul_separated_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    completed = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="a.py\0pkg/b.py\0", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: completed)

    assert check_repo_policy.tracked_files(tmp_path) == ["a.py", "pkg/b.py"]


def test_missing_workflows_directory_passes(tmp_path: Path) -> None:
    assert check_repo_policy.check_workflow_actions_pinned(tmp_path) == []


def test_unpinned_action_is_reported(tmp_path: Path) -> None:
    write_file(
        tmp_path,
        ".github/workflows/ci.yml",
        "jobs:\n  quality:\n    steps:\n      - uses: actions/checkout@v7\n",
    )

    violations = check_repo_policy.check_workflow_actions_pinned(tmp_path)

    assert len(violations) == 1
    assert "actions/checkout@v7" in violations[0]


def test_pinned_and_local_actions_pass(tmp_path: Path) -> None:
    write_file(
        tmp_path,
        ".github/workflows/ci.yml",
        "jobs:\n"
        "  quality:\n"
        "    steps:\n"
        f"      - uses: actions/checkout@{'a' * 40} # v7.0.1\n"
        "      - uses: ./.github/actions/local\n"
        "      - uses: docker://alpine:3.20\n",
    )

    assert check_repo_policy.check_workflow_actions_pinned(tmp_path) == []


def test_markdown_links_report_missing_targets(tmp_path: Path) -> None:
    write_file(
        tmp_path,
        "README.md",
        "See [guide](docs/guide.md) and [site](https://example.test/docs).\n",
    )

    violations = check_repo_policy.check_markdown_links(tmp_path)

    assert len(violations) == 1
    assert "docs/guide.md" in violations[0]


def test_markdown_links_accept_existing_paths_and_anchors(tmp_path: Path) -> None:
    write_file(tmp_path, "docs/guide.md", "# Guide\n")
    write_file(tmp_path, "README.md", "[a](docs/guide.md#usage) [b](#top) [c](/docs/guide.md)\n")

    assert check_repo_policy.check_markdown_links(tmp_path) == []


def test_markdown_links_ignore_generated_directories(tmp_path: Path) -> None:
    write_file(tmp_path, "node_modules/pkg/README.md", "[broken](missing.md)\n")
    write_file(tmp_path, ".git/README.md", "[broken](missing.md)\n")

    assert check_repo_policy.check_markdown_links(tmp_path) == []


def test_relative_links_skip_external_anchors_and_templates(tmp_path: Path) -> None:
    document = write_file(
        tmp_path,
        "notes.md",
        "[a](https://example.test) [b](#anchor) [c](mailto:ops@example.test) [d]({{ var }})\n",
    )

    assert check_repo_policy.relative_links(document) == []


def test_relative_links_return_local_targets(tmp_path: Path) -> None:
    document = write_file(tmp_path, "notes.md", "[a](docs/guide.md) [b](https://example.test)\n")

    assert check_repo_policy.relative_links(document) == ["docs/guide.md"]


def test_codeowners_missing_file(tmp_path: Path) -> None:
    assert check_repo_policy.check_codeowners_default_rule(tmp_path) == [
        "missing .github/CODEOWNERS"
    ]


def test_codeowners_requires_default_rule(tmp_path: Path) -> None:
    write_file(tmp_path, ".github/CODEOWNERS", "/infra/ @someone\n")

    violations = check_repo_policy.check_codeowners_default_rule(tmp_path)

    assert violations == [".github/CODEOWNERS has no default catch-all rule (`* @owner`)"]


def test_codeowners_accepts_default_rule_with_comments(tmp_path: Path) -> None:
    write_file(tmp_path, ".github/CODEOWNERS", "# * @ignored\n* @owner\n")

    assert check_repo_policy.check_codeowners_default_rule(tmp_path) == []


def test_run_checks_quiet_prints_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check_repo_policy, "tracked_files", lambda _root: [])

    violations = check_repo_policy.run_checks(tmp_path, quiet=True)

    assert violations
    assert capsys.readouterr().out == ""


def test_main_reports_success(capsys: pytest.CaptureFixture[str]) -> None:
    assert check_repo_policy.main(["--root", str(REPO_ROOT)]) == 0
    assert "repository policy check passed" in capsys.readouterr().out


def test_main_reports_violations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check_repo_policy, "tracked_files", lambda _root: [])

    assert check_repo_policy.main(["--root", str(tmp_path)]) == 1
    assert "repository policy check failed" in capsys.readouterr().out


def test_main_returns_two_when_the_root_is_not_a_git_repository(tmp_path: Path) -> None:
    """An unverifiable repository is an error, never a silent pass."""
    exit_code = check_repo_policy.main(["--root", str(tmp_path), "--quiet"])

    assert exit_code == 2


def test_main_returns_two_when_checks_cannot_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def failing_checks(_root: Path, quiet: bool = False) -> list[str]:
        raise RuntimeError("git is not installed")

    monkeypatch.setattr(check_repo_policy, "run_checks", failing_checks)

    assert check_repo_policy.main(["--root", str(tmp_path)]) == 2
    assert "could not run" in capsys.readouterr().err
