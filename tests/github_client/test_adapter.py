"""Tests for GitHub adapter."""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from packages.github_client.adapter import GitHubAdapter, GitHubConfig


@pytest.fixture
def github_config() -> GitHubConfig:
    """Return a GitHub configuration for testing."""
    return GitHubConfig(
        token="test-token",
        owner="test-owner",
        repo="test-repo",
    )


@pytest.fixture
def adapter(github_config: GitHubConfig, offline_github_client: httpx.AsyncClient) -> GitHubAdapter:
    """Return a GitHub adapter bound to the offline GitHub transport."""
    return GitHubAdapter(github_config, client=offline_github_client)


@pytest.mark.unit
def test_adapter_initialization(github_config: GitHubConfig) -> None:
    """Test that adapter initializes with valid config."""
    adapter = GitHubAdapter(github_config)
    assert adapter.config.owner == "test-owner"
    assert adapter.config.repo == "test-repo"


@pytest.mark.unit
def test_adapter_requires_owner() -> None:
    """Test that adapter requires owner in config."""
    config = GitHubConfig(token="test", repo="test-repo")
    with pytest.raises(ValueError, match="owner"):
        GitHubAdapter(config)


@pytest.mark.unit
def test_adapter_requires_repo() -> None:
    """Test that adapter requires repo in config."""
    config = GitHubConfig(token="test", owner="test-owner")
    with pytest.raises(ValueError, match="repo"):
        GitHubAdapter(config)


@pytest.mark.unit
async def test_get_repository_metadata(adapter: GitHubAdapter) -> None:
    """Test retrieving repository metadata."""
    metadata = await adapter.get_repository_metadata()

    assert isinstance(metadata, dict)
    assert metadata["owner"] == "test-owner"
    assert metadata["repo"] == "test-repo"
    assert "default_branch" in metadata


@pytest.mark.unit
async def test_get_commit_history(adapter: GitHubAdapter) -> None:
    """Test retrieving commit history."""
    commits = await adapter.get_commit_history(limit=10)

    assert isinstance(commits, list)


@pytest.mark.unit
async def test_get_commit_history_with_time_range(adapter: GitHubAdapter) -> None:
    """Test retrieving commit history with time constraints."""
    since = datetime(2024, 1, 1)
    until = datetime(2024, 12, 31)

    commits = await adapter.get_commit_history(since=since, until=until, limit=50)

    assert isinstance(commits, list)


@pytest.mark.unit
async def test_get_deployment_history(adapter: GitHubAdapter) -> None:
    """Test retrieving deployment history."""
    deployments = await adapter.get_deployment_history(environment="production", limit=20)

    assert isinstance(deployments, list)


@pytest.mark.unit
async def test_create_issue(adapter: GitHubAdapter) -> None:
    """Test creating a GitHub issue."""
    issue = await adapter.create_issue(
        title="Test Issue",
        body="This is a test issue",
        labels=["bug", "incident"],
    )

    assert issue.title == "Test Issue"
    assert issue.body == "This is a test issue"
    assert issue.state == "open"
    assert issue.number > 0
    assert issue.url


@pytest.mark.unit
async def test_create_pull_request(adapter: GitHubAdapter) -> None:
    """Test creating a pull request."""
    pr = await adapter.create_pull_request(
        title="Fix incident INC-001",
        body="This PR addresses incident INC-001",
        head_branch="fix/inc-001",
        base_branch="main",
    )

    assert pr.title == "Fix incident INC-001"
    assert pr.head_branch == "fix/inc-001"
    assert pr.base_branch == "main"
    assert pr.state == "open"
    assert pr.number > 0


@pytest.mark.unit
async def test_create_draft_pull_request(adapter: GitHubAdapter) -> None:
    """Test creating a draft pull request."""
    pr = await adapter.create_pull_request(
        title="WIP: Fix",
        body="Work in progress",
        head_branch="wip",
        draft=True,
    )

    assert pr.number > 0


@pytest.mark.unit
async def test_update_pull_request(adapter: GitHubAdapter) -> None:
    """Test updating an existing pull request."""
    updated_pr = await adapter.update_pull_request(
        pr_number=42,
        body="Updated description with more details",
    )

    assert updated_pr.number == 42
    assert updated_pr.body == "Updated description with more details"


@pytest.mark.unit
async def test_update_pull_request_state(adapter: GitHubAdapter) -> None:
    """Test closing a pull request."""
    updated_pr = await adapter.update_pull_request(pr_number=42, state="closed")

    assert updated_pr.state == "closed"


@pytest.mark.unit
async def test_get_check_status(adapter: GitHubAdapter) -> None:
    """Test retrieving CI check status."""
    status = await adapter.get_check_status(ref="abc123")

    assert isinstance(status, dict)
    assert "status" in status
    assert "conclusion" in status
