"""Integration tests for GitHub adapter with mocked HTTP responses."""

from datetime import datetime, timezone
import pytest
import respx
from httpx import Response

from packages.github_client.adapter import (
    GitHubAdapter,
    GitHubConfig,
    GitHubCommit,
    GitHubDeployment,
    GitHubIssue,
    GitHubPullRequest,
    GitHubCheckRun,
)


@pytest.fixture
def github_config() -> GitHubConfig:
    """Create a test GitHub configuration."""
    return GitHubConfig(
        token="gh_test_token_123",
        owner="testowner",
        repo="testrepo",
        api_base_url="https://api.github.com",
    )


@pytest.fixture
def adapter(github_config: GitHubConfig) -> GitHubAdapter:
    """Create a GitHub adapter instance."""
    return GitHubAdapter(github_config)


@pytest.mark.asyncio
@respx.mock
async def test_get_repository_metadata(adapter: GitHubAdapter) -> None:
    """Test fetching repository metadata."""
    mock_response = {
        "name": "testrepo",
        "owner": {"login": "testowner"},
        "default_branch": "main",
        "private": False,
        "description": "A test repository",
        "language": "Python",
        "stargazers_count": 42,
        "forks_count": 7,
    }

    respx.get("https://api.github.com/repos/testowner/testrepo").mock(
        return_value=Response(200, json=mock_response)
    )

    result = await adapter.get_repository_metadata()

    assert result["owner"] == "testowner"
    assert result["repo"] == "testrepo"
    assert result["default_branch"] == "main"
    assert result["private"] is False
    assert result["description"] == "A test repository"
    assert result["language"] == "Python"
    assert result["stars"] == 42
    assert result["forks"] == 7


@pytest.mark.asyncio
@respx.mock
async def test_get_commit_history(adapter: GitHubAdapter) -> None:
    """Test fetching commit history."""
    mock_response = [
        {
            "sha": "abc123def456",
            "commit": {
                "message": "fix: resolve critical bug",
                "author": {
                    "name": "John Doe",
                    "date": "2024-01-15T10:30:00Z",
                },
            },
            "html_url": "https://github.com/testowner/testrepo/commit/abc123def456",
        },
        {
            "sha": "def456ghi789",
            "commit": {
                "message": "feat: add new feature",
                "author": {
                    "name": "Jane Smith",
                    "date": "2024-01-14T14:20:00Z",
                },
            },
            "html_url": "https://github.com/testowner/testrepo/commit/def456ghi789",
        },
    ]

    respx.get("https://api.github.com/repos/testowner/testrepo/commits").mock(
        return_value=Response(200, json=mock_response)
    )

    commits = await adapter.get_commit_history(limit=10)

    assert len(commits) == 2
    assert isinstance(commits[0], GitHubCommit)
    assert commits[0].sha == "abc123def456"
    assert commits[0].message == "fix: resolve critical bug"
    assert commits[0].author == "John Doe"
    assert commits[0].url == "https://github.com/testowner/testrepo/commit/abc123def456"
    assert commits[1].sha == "def456ghi789"


@pytest.mark.asyncio
@respx.mock
async def test_get_commit_history_with_date_range(adapter: GitHubAdapter) -> None:
    """Test fetching commit history with date filters."""
    mock_response = [
        {
            "sha": "abc123",
            "commit": {
                "message": "fix: bug",
                "author": {"name": "Dev", "date": "2024-01-15T10:00:00Z"},
            },
            "html_url": "https://github.com/testowner/testrepo/commit/abc123",
        }
    ]

    route = respx.get("https://api.github.com/repos/testowner/testrepo/commits").mock(
        return_value=Response(200, json=mock_response)
    )

    since = datetime(2024, 1, 10, tzinfo=timezone.utc)
    until = datetime(2024, 1, 20, tzinfo=timezone.utc)

    commits = await adapter.get_commit_history(since=since, until=until, limit=50)

    assert len(commits) == 1
    assert route.called
    # Verify query params were passed
    assert "since" in str(route.calls.last.request.url)
    assert "until" in str(route.calls.last.request.url)


@pytest.mark.asyncio
@respx.mock
async def test_get_deployment_history(adapter: GitHubAdapter) -> None:
    """Test fetching deployment history."""
    mock_response = [
        {
            "id": 12345,
            "environment": "production",
            "sha": "abc123def456",
            "ref": "refs/heads/main",
            "creator": {"login": "deploy-bot"},
            "created_at": "2024-01-15T12:00:00Z",
            "updated_at": "2024-01-15T12:05:00Z",
            "statuses_url": "https://api.github.com/repos/testowner/testrepo/deployments/12345/statuses",
            "description": "Production deployment v1.2.3",
        },
        {
            "id": 12346,
            "environment": "production",
            "sha": "def456ghi789",
            "ref": "refs/heads/main",
            "creator": {"login": "deploy-bot"},
            "created_at": "2024-01-14T10:00:00Z",
            "updated_at": "2024-01-14T10:03:00Z",
            "statuses_url": "https://api.github.com/repos/testowner/testrepo/deployments/12346/statuses",
            "description": "Production deployment v1.2.2",
        },
    ]

    respx.get("https://api.github.com/repos/testowner/testrepo/deployments").mock(
        return_value=Response(200, json=mock_response)
    )

    deployments = await adapter.get_deployment_history(environment="production", limit=10)

    assert len(deployments) == 2
    assert isinstance(deployments[0], GitHubDeployment)
    assert deployments[0].id == 12345
    assert deployments[0].environment == "production"
    assert deployments[0].sha == "abc123def456"
    assert deployments[0].creator == "deploy-bot"
    assert deployments[0].description == "Production deployment v1.2.3"


@pytest.mark.asyncio
@respx.mock
async def test_create_issue(adapter: GitHubAdapter) -> None:
    """Test creating a GitHub issue."""
    mock_response = {
        "number": 42,
        "title": "Critical bug found",
        "body": "This is a critical bug that needs fixing",
        "state": "open",
        "html_url": "https://github.com/testowner/testrepo/issues/42",
        "created_at": "2024-01-15T10:00:00Z",
        "labels": [
            {"name": "bug"},
            {"name": "critical"},
        ],
    }

    route = respx.post("https://api.github.com/repos/testowner/testrepo/issues").mock(
        return_value=Response(201, json=mock_response)
    )

    issue = await adapter.create_issue(
        title="Critical bug found",
        body="This is a critical bug that needs fixing",
        labels=["bug", "critical"],
    )

    assert isinstance(issue, GitHubIssue)
    assert issue.number == 42
    assert issue.title == "Critical bug found"
    assert issue.state == "open"
    assert issue.url == "https://github.com/testowner/testrepo/issues/42"
    assert issue.labels == ["bug", "critical"]
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_create_pull_request(adapter: GitHubAdapter) -> None:
    """Test creating a pull request."""
    mock_response = {
        "number": 123,
        "title": "Add new feature",
        "body": "This PR adds a new feature",
        "state": "open",
        "head": {"ref": "feature-branch"},
        "base": {"ref": "main"},
        "html_url": "https://github.com/testowner/testrepo/pull/123",
        "created_at": "2024-01-15T10:00:00Z",
        "draft": False,
        "mergeable": True,
    }

    route = respx.post("https://api.github.com/repos/testowner/testrepo/pulls").mock(
        return_value=Response(201, json=mock_response)
    )

    pr = await adapter.create_pull_request(
        title="Add new feature",
        body="This PR adds a new feature",
        head_branch="feature-branch",
        base_branch="main",
        draft=False,
    )

    assert isinstance(pr, GitHubPullRequest)
    assert pr.number == 123
    assert pr.title == "Add new feature"
    assert pr.state == "open"
    assert pr.head_branch == "feature-branch"
    assert pr.base_branch == "main"
    assert pr.draft is False
    assert pr.mergeable is True
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_create_draft_pull_request(adapter: GitHubAdapter) -> None:
    """Test creating a draft pull request."""
    mock_response = {
        "number": 124,
        "title": "WIP: New feature",
        "body": "Work in progress",
        "state": "open",
        "head": {"ref": "wip-branch"},
        "base": {"ref": "main"},
        "html_url": "https://github.com/testowner/testrepo/pull/124",
        "created_at": "2024-01-15T11:00:00Z",
        "draft": True,
        "mergeable": None,
    }

    respx.post("https://api.github.com/repos/testowner/testrepo/pulls").mock(
        return_value=Response(201, json=mock_response)
    )

    pr = await adapter.create_pull_request(
        title="WIP: New feature",
        body="Work in progress",
        head_branch="wip-branch",
        base_branch="main",
        draft=True,
    )

    assert pr.draft is True
    assert pr.mergeable is None


@pytest.mark.asyncio
@respx.mock
async def test_get_check_runs(adapter: GitHubAdapter) -> None:
    """Test fetching check runs for a commit."""
    mock_response = {
        "total_count": 2,
        "check_runs": [
            {
                "id": 1001,
                "name": "CI Tests",
                "status": "completed",
                "conclusion": "success",
                "started_at": "2024-01-15T10:00:00Z",
                "completed_at": "2024-01-15T10:15:00Z",
                "output": {
                    "title": "All tests passed",
                    "summary": "127 tests passed, 0 failed",
                },
            },
            {
                "id": 1002,
                "name": "Lint",
                "status": "completed",
                "conclusion": "success",
                "started_at": "2024-01-15T10:00:00Z",
                "completed_at": "2024-01-15T10:02:00Z",
                "output": {
                    "title": "No linting errors",
                    "summary": "All files pass linting",
                },
            },
        ],
    }

    respx.get("https://api.github.com/repos/testowner/testrepo/commits/abc123/check-runs").mock(
        return_value=Response(200, json=mock_response)
    )

    check_runs = await adapter.get_check_runs(ref="abc123")

    assert len(check_runs) == 2
    assert isinstance(check_runs[0], GitHubCheckRun)
    assert check_runs[0].id == 1001
    assert check_runs[0].name == "CI Tests"
    assert check_runs[0].status == "completed"
    assert check_runs[0].conclusion == "success"
    assert check_runs[0].output_title == "All tests passed"
    assert check_runs[0].output_summary == "127 tests passed, 0 failed"


@pytest.mark.asyncio
@respx.mock
async def test_get_check_runs_in_progress(adapter: GitHubAdapter) -> None:
    """Test fetching check runs that are still in progress."""
    mock_response = {
        "total_count": 1,
        "check_runs": [
            {
                "id": 2001,
                "name": "Build",
                "status": "in_progress",
                "conclusion": None,
                "started_at": "2024-01-15T10:00:00Z",
                "completed_at": None,
                "output": {},
            }
        ],
    }

    respx.get("https://api.github.com/repos/testowner/testrepo/commits/def456/check-runs").mock(
        return_value=Response(200, json=mock_response)
    )

    check_runs = await adapter.get_check_runs(ref="def456")

    assert len(check_runs) == 1
    assert check_runs[0].status == "in_progress"
    assert check_runs[0].conclusion is None
    assert check_runs[0].completed_at is None


@pytest.mark.asyncio
async def test_adapter_context_manager(github_config: GitHubConfig) -> None:
    """Test using the adapter as a context manager."""
    async with GitHubAdapter(github_config) as adapter:
        assert adapter._client is None  # Not created until first use

    # Client should be closed after exiting context
    assert adapter._client is None or adapter._client.is_closed


@pytest.mark.asyncio
@respx.mock
async def test_http_error_handling(adapter: GitHubAdapter) -> None:
    """Test that HTTP errors are properly raised."""
    respx.get("https://api.github.com/repos/testowner/testrepo").mock(
        return_value=Response(404, json={"message": "Not Found"})
    )

    with pytest.raises(Exception):  # httpx.HTTPStatusError
        await adapter.get_repository_metadata()


@pytest.mark.asyncio
@respx.mock
async def test_malformed_response_handling(adapter: GitHubAdapter) -> None:
    """Test handling of malformed API responses."""
    # Response missing required fields
    mock_response = [
        {
            "sha": "abc123",
            # Missing "commit" field
            "html_url": "https://github.com/testowner/testrepo/commit/abc123",
        }
    ]

    respx.get("https://api.github.com/repos/testowner/testrepo/commits").mock(
        return_value=Response(200, json=mock_response)
    )

    commits = await adapter.get_commit_history()

    # Should return empty list, logging warning about parse failure
    assert len(commits) == 0


@pytest.mark.asyncio
async def test_close_adapter(adapter: GitHubAdapter) -> None:
    """Test explicitly closing the adapter."""
    await adapter.close()
    assert adapter._client is None


def test_adapter_validation() -> None:
    """Test that adapter validates configuration."""
    with pytest.raises(ValueError, match="GitHub owner is required"):
        GitHubAdapter(GitHubConfig(token="test", owner="", repo="testrepo"))

    with pytest.raises(ValueError, match="GitHub repo is required"):
        GitHubAdapter(GitHubConfig(token="test", owner="testowner", repo=""))
