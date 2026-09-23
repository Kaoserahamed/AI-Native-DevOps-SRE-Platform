"""Offline GitHub transport shared by the adapter tests.

Every test in this directory talks to a **real** ``httpx.AsyncClient`` whose transport is an
``httpx.MockTransport``. That is deliberate: request building, header construction, response
parsing and error handling are exactly the code under test, so the only thing replaced is the
network. Without this, the adapter tests reach ``api.github.com`` unauthenticated, fail with a 401
and pass or fail depending on whether the machine has egress — a test that lies.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import pytest

from packages.github_client.adapter import GitHubAdapter, GitHubConfig

#: ``/repos/{owner}/{repo}`` and nothing deeper — matched last so the deeper routes win.
REPOSITORY_PATH = re.compile(r"^/repos/(?P<owner>[^/]+)/(?P<repo>[^/]+)$")

#: Commit author timestamps the mock returns, in GitHub's ``Z``-suffixed form.
_TIMESTAMP = "2024-01-15T10:00:00Z"


def _json_body(request: httpx.Request) -> dict[str, Any]:
    """Return the decoded JSON request body (empty for a request without one)."""
    if not request.content:
        return {}
    payload = json.loads(request.content.decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _repo_prefix(path: str) -> str:
    """Return the ``/repos/{owner}/{repo}`` prefix of a GitHub API path."""
    parts = path.split("/")
    return f"/repos/{parts[2]}/{parts[3]}"


def github_response(request: httpx.Request) -> httpx.Response:
    """Return a deterministic GitHub-shaped response for one request.

    The handler echoes what the request asked for (the repository in the path, the pull request
    number, the body the caller sent) so an assertion about a response is really an assertion about
    the request the adapter built.
    """

    def reply(payload: Any, status_code: int = 200) -> httpx.Response:
        return httpx.Response(status_code, json=payload, request=request)

    path = request.url.path
    method = request.method
    body = _json_body(request)
    prefix = _repo_prefix(path)

    # --- git data API (branch and commit workflows) ---
    if path.startswith(f"{prefix}/git/ref/heads/"):
        return reply({"object": {"sha": "base-sha"}})
    if path.startswith(f"{prefix}/git/commits/"):
        return reply({"sha": "base-sha", "tree": {"sha": "base-tree"}})
    if path.endswith("/git/commits") and method == "POST":
        return reply({"sha": "commit-sha"})
    if path.endswith("/git/blobs"):
        return reply({"sha": "blob-sha"})
    if path.endswith("/git/trees"):
        return reply({"sha": "tree-sha"})
    if "/git/refs/heads/" in path or path.endswith("/git/refs"):
        return reply({"object": {"sha": "commit-sha"}})

    # --- checks ---
    if path.endswith("/check-runs"):
        return reply({"check_runs": []})

    # --- issues and comments ---
    if path.endswith("/issues") and method == "POST":
        return reply(
            {
                "number": 42,
                "title": body.get("title", "Test Issue"),
                "body": body.get("body", ""),
                "state": "open",
                "html_url": "https://github.com/test-org/test-repo/issues/42",
                "created_at": _TIMESTAMP,
                "labels": [{"name": label} for label in body.get("labels", [])],
            }
        )
    if "/issues/" in path and path.endswith("/comments"):
        return reply({"id": 1})

    # --- pull requests ---
    if "/pulls/" in path and method == "PATCH":
        number = int(path.rsplit("/", 1)[-1])
        return reply(_pull_request_payload(number, body))
    if path.endswith("/pulls") and method == "POST":
        return reply(_pull_request_payload(123, body))

    # --- history collections ---
    if path.endswith("/commits"):
        return reply([])
    if path.endswith("/deployments"):
        return reply([])

    # --- repository metadata ---
    repository_match = REPOSITORY_PATH.match(path)
    if repository_match:
        return reply(
            {
                "owner": {"login": repository_match.group("owner")},
                "name": repository_match.group("repo"),
                "default_branch": "main",
                "private": False,
                "description": "Test repository",
                "language": "Python",
                "stargazers_count": 1,
                "forks_count": 2,
            }
        )

    return reply({})


def _pull_request_payload(number: int, body: dict[str, Any]) -> dict[str, Any]:
    """Return the pull-request payload GitHub would answer a create/update with."""
    return {
        "number": number,
        "title": body.get("title", "Test PR"),
        "body": body.get("body", ""),
        "state": body.get("state", "open"),
        "html_url": f"https://github.com/test-org/test-repo/pull/{number}",
        "head": {"ref": body.get("head", "feature-branch")},
        "base": {"ref": body.get("base", "main")},
        "created_at": _TIMESTAMP,
        "draft": body.get("draft", False),
    }

def offline_client(config: GitHubConfig) -> httpx.AsyncClient:
    """Return a client that answers GitHub requests from :func:`github_response`."""
    return httpx.AsyncClient(
        base_url=config.api_base_url,
        headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        transport=httpx.MockTransport(github_response),
    )


@pytest.fixture
def github_config() -> GitHubConfig:
    """Return a GitHub configuration for the offline transport."""
    return GitHubConfig(token="test-token", owner="test-owner", repo="test-repo")


@pytest.fixture
def offline_github_client(github_config: GitHubConfig) -> httpx.AsyncClient:
    """Return a real ``httpx.AsyncClient`` wired to the offline transport."""
    return offline_client(github_config)


@pytest.fixture(autouse=True)
def keep_github_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every adapter created in this directory use the offline transport.

    An adapter that builds its own client lazily would otherwise reach the real API. Patching the
    single method that creates the client keeps the adapter's public behaviour untouched while
    guaranteeing that a missing egress route can never turn a GitHub test red.
    """

    async def get_client(adapter: GitHubAdapter) -> httpx.AsyncClient:
        client = adapter._client
        if client is None:
            client = offline_client(adapter.config)
            adapter._client = client
        return client

    monkeypatch.setattr(GitHubAdapter, "_get_client", get_client)
