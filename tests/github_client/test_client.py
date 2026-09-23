"""Offline REST contract tests for the typed GitHub client."""

import httpx
import pytest

from packages.github_client import GitHubClient


@pytest.mark.asyncio
async def test_get_repository_maps_response_and_sends_auth() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "owner": {"login": "acme"},
                "name": "platform",
                "default_branch": "main",
                "private": True,
                "html_url": "https://github.com/acme/platform",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://api.github.test") as client:
        github = GitHubClient(token="test-token", owner="acme", repo="platform", client=client)
        repository = await github.get_repository()

    assert repository.owner == "acme"
    assert repository.default_branch == "main"
    assert requests[0].url.path == "/repos/acme/platform"
    assert requests[0].headers["Authorization"] == "Bearer test-token"


@pytest.mark.asyncio
async def test_create_issue_posts_typed_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/repos/acme/platform/issues"
        assert request.read() == b'{"title":"Incident","body":"Details","labels":["incident"]}'
        return httpx.Response(
            201,
            json={
                "number": 7,
                "title": "Incident",
                "body": "Details",
                "state": "open",
                "html_url": "https://github.com/acme/platform/issues/7",
                "created_at": "2026-09-23T12:00:00Z",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://api.github.test") as client:
        github = GitHubClient(owner="acme", repo="platform", client=client)
        issue = await github.create_issue("Incident", "Details", ["incident"])

    assert issue.number == 7
    assert issue.created_at.year == 2026


@pytest.mark.asyncio
async def test_create_pull_request_maps_nested_branches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={
                "number": 8,
                "title": "Fix",
                "body": "Details",
                "state": "open",
                "html_url": "https://github.com/acme/platform/pull/8",
                "head": {"ref": "fix/incident"},
                "base": {"ref": "main"},
                "draft": False,
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://api.github.test") as client:
        github = GitHubClient(owner="acme", repo="platform", client=client)
        pull_request = await github.create_pull_request("Fix", "Details", "fix/incident")

    assert pull_request.head_branch == "fix/incident"
    assert pull_request.base_branch == "main"
