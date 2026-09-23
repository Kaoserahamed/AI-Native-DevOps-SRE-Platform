"""Offline HTTP responses for the legacy adapter tests."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from packages.github_client.adapter import GitHubAdapter


class MockGitHubClient:
    """Minimal async client returning deterministic GitHub-shaped responses."""

    def _response(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        payload = request.content
        body: dict[str, Any] = {}

        if path.endswith("/git/ref/heads/main") or "/git/ref/heads/feature" in path:
            body = {"object": {"sha": "base-sha"}}
        elif "/git/commits/base-sha" in path:
            body = {"sha": "base-sha", "tree": {"sha": "base-tree"}}
        elif path.endswith("/git/blobs"):
            body = {"sha": "blob-sha"}
        elif path.endswith("/git/trees"):
            body = {"sha": "tree-sha"}
        elif path.endswith("/git/commits"):
            body = {"sha": "commit-sha"}
        elif "/git/refs/heads/" in path:
            body = {"object": {"sha": "commit-sha"}}
        elif path.endswith("/pulls") or "/pulls/" in path:
            request_data = self._json(payload)
            number = 123
            body = {
                "number": number,
                "title": request_data.get("title", "Test PR"),
                "body": request_data.get("body", "Updated PR body"),
                "state": request_data.get("state", "open"),
                "html_url": f"https://github.com/test-org/test-repo/pull/{number}",
                "head": {"ref": request_data.get("head", "feature-branch")},
                "base": {"ref": request_data.get("base", "main")},
                "created_at": "2024-01-15T10:00:00Z",
                "draft": request_data.get("draft", False),
            }
        elif path.endswith("/issues"):
            request_data = self._json(payload)
            body = {
                "number": 42,
                "title": request_data.get("title", "Test Issue"),
                "body": request_data.get("body", "This is a test issue body"),
                "state": "open",
                "html_url": "https://github.com/test-org/test-repo/issues/42",
                "created_at": "2024-01-15T10:00:00Z",
                "labels": [{"name": label} for label in request_data.get("labels", [])],
            }
        elif "/issues/" in path and path.endswith("/comments"):
            body = {"id": 1}
        elif path.endswith("/check-runs"):
            body = {"check_runs": []}
        elif path.endswith("/commits") or path.endswith("/deployments"):
            body = []
        elif path == "/repos/test-org/test-repo":
            body = {
                "owner": {"login": "test-org"},
                "name": "test-repo",
                "default_branch": "main",
                "private": False,
                "description": "Test repository",
                "language": "Python",
                "stargazers_count": 1,
                "forks_count": 2,
            }

        return httpx.Response(200, json=body, request=request)

    @staticmethod
    def _json(payload: bytes) -> dict[str, Any]:
        import json

        return json.loads(payload.decode("utf-8")) if payload else {}

    async def get(self, url: str, **_kwargs: Any) -> httpx.Response:
        return self._response(httpx.Request("GET", url))

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        import json

        request = httpx.Request(
            "POST",
            url,
            content=json.dumps(kwargs.get("json", {})).encode("utf-8"),
        )
        return self._response(request)

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        import json

        request = httpx.Request(
            "PATCH",
            url,
            content=json.dumps(kwargs.get("json", {})).encode("utf-8"),
        )
        return self._response(request)


@pytest.fixture(autouse=True)
def mock_github_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep adapter tests offline and independent of GitHub credentials."""

    async def get_client(_: GitHubAdapter) -> MockGitHubClient:
        return MockGitHubClient()

    monkeypatch.setattr(GitHubAdapter, "_get_client", get_client)
