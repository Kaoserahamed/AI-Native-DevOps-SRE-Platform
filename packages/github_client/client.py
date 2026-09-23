"""Small, typed GitHub REST client used by platform services."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict


class GitHubRepository(BaseModel):
    """Repository metadata returned by GitHub."""

    model_config = ConfigDict(extra="ignore")

    owner: str
    name: str
    default_branch: str
    private: bool
    html_url: str


class GitHubIssue(BaseModel):
    """Issue data returned by GitHub."""

    model_config = ConfigDict(extra="ignore")

    number: int
    title: str
    body: str | None = None
    state: str
    html_url: str
    created_at: datetime


class GitHubPullRequest(BaseModel):
    """Pull request data returned by GitHub."""

    model_config = ConfigDict(extra="ignore")

    number: int
    title: str
    body: str | None = None
    state: str
    html_url: str
    head_branch: str
    base_branch: str
    draft: bool = False


class GitHubClient:
    """Typed, asynchronous wrapper around the small GitHub REST surface we use."""

    def __init__(
        self,
        token: str | None = None,
        *,
        owner: str,
        repo: str,
        api_base_url: str = "https://api.github.com",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not owner or not repo:
            raise ValueError("owner and repo are required")
        self.owner = owner
        self.repo = repo
        if client is None:
            self._client = httpx.AsyncClient(
                base_url=api_base_url,
                headers=self._headers(token),
                timeout=30.0,
            )
        else:
            client.headers.update(self._headers(token))
            self._client = client
        self._owns_client = client is None

    @staticmethod
    def _headers(token: str | None) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @property
    def _repo_path(self) -> str:
        return f"/repos/{self.owner}/{self.repo}"

    async def close(self) -> None:
        """Close the underlying client when this wrapper created it."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> GitHubClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        await self.close()

    async def get_repository(self) -> GitHubRepository:
        """Fetch repository metadata."""
        response = await self._client.get(self._repo_path)
        response.raise_for_status()
        data = response.json()
        return GitHubRepository(
            owner=data["owner"]["login"],
            name=data["name"],
            default_branch=data["default_branch"],
            private=data["private"],
            html_url=data["html_url"],
        )

    async def create_issue(
        self, title: str, body: str, labels: list[str] | None = None
    ) -> GitHubIssue:
        """Create an issue in the configured repository."""
        response = await self._client.post(
            f"{self._repo_path}/issues",
            json={"title": title, "body": body, "labels": labels or []},
        )
        response.raise_for_status()
        data = response.json()
        return GitHubIssue.model_validate(data)

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        draft: bool = False,
    ) -> GitHubPullRequest:
        """Create a pull request in the configured repository."""
        response = await self._client.post(
            f"{self._repo_path}/pulls",
            json={"title": title, "body": body, "head": head, "base": base, "draft": draft},
        )
        response.raise_for_status()
        data = response.json()
        return GitHubPullRequest(
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            state=data["state"],
            html_url=data["html_url"],
            head_branch=data["head"]["ref"],
            base_branch=data["base"]["ref"],
            draft=data.get("draft", False),
        )
