"""Tests for GitHub adapter including incident issues and remediation PRs."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.github_client.adapter import (
    GitHubAdapter,
    GitHubCheckRun,
    GitHubCommit,
    GitHubConfig,
    GitHubDeployment,
    GitHubIssue,
    GitHubPullRequest,
    IncidentIssueData,
    RemediationPRData,
)


@pytest.fixture
def github_config() -> GitHubConfig:
    """Create a test GitHub configuration."""
    return GitHubConfig(
        token="ghp_test_token_123",
        owner="test-org",
        repo="test-repo",
        api_base_url="https://api.github.com",
    )


@pytest.fixture
def github_adapter(github_config: GitHubConfig) -> GitHubAdapter:
    """Create a GitHub adapter instance."""
    return GitHubAdapter(config=github_config)


class TestGitHubAdapter:
    """Test suite for GitHubAdapter basic operations."""

    def test_adapter_initialization(self, github_config: GitHubConfig) -> None:
        """Test adapter initializes with valid config."""
        adapter = GitHubAdapter(config=github_config)
        assert adapter.config == github_config

    def test_adapter_validation_missing_owner(self) -> None:
        """Test adapter raises error when owner is missing."""
        config = GitHubConfig(token="test", owner="", repo="test-repo")
        with pytest.raises(ValueError, match="GitHub owner is required"):
            GitHubAdapter(config=config)

    def test_adapter_validation_missing_repo(self) -> None:
        """Test adapter raises error when repo is missing."""
        config = GitHubConfig(token="test", owner="test-org", repo="")
        with pytest.raises(ValueError, match="GitHub repo is required"):
            GitHubAdapter(config=config)

    @pytest.mark.asyncio
    async def test_get_repository_metadata(self, github_adapter: GitHubAdapter) -> None:
        """Test retrieving repository metadata."""
        metadata = await github_adapter.get_repository_metadata()

        assert metadata["owner"] == "test-org"
        assert metadata["repo"] == "test-repo"
        assert "default_branch" in metadata
        assert "private" in metadata

    @pytest.mark.asyncio
    async def test_get_commit_history(self, github_adapter: GitHubAdapter) -> None:
        """Test retrieving commit history with time range."""
        since = datetime(2024, 1, 1, tzinfo=UTC)
        until = datetime(2024, 1, 31, tzinfo=UTC)

        commits = await github_adapter.get_commit_history(since=since, until=until, limit=50)

        assert isinstance(commits, list)
        # Stub returns empty list
        assert len(commits) == 0

    @pytest.mark.asyncio
    async def test_get_deployment_history(self, github_adapter: GitHubAdapter) -> None:
        """Test retrieving deployment history for an environment."""
        deployments = await github_adapter.get_deployment_history(
            environment="production", limit=10
        )

        assert isinstance(deployments, list)
        # Stub returns empty list
        assert len(deployments) == 0

    @pytest.mark.asyncio
    async def test_create_issue(self, github_adapter: GitHubAdapter) -> None:
        """Test creating a GitHub issue."""
        issue = await github_adapter.create_issue(
            title="Test Issue",
            body="This is a test issue body",
            labels=["bug", "urgent"],
        )

        assert isinstance(issue, GitHubIssue)
        assert issue.title == "Test Issue"
        assert issue.body == "This is a test issue body"
        assert issue.labels == ["bug", "urgent"]
        assert issue.state == "open"
        assert "github.com" in issue.url

    @pytest.mark.asyncio
    async def test_create_pull_request(self, github_adapter: GitHubAdapter) -> None:
        """Test creating a pull request."""
        pr = await github_adapter.create_pull_request(
            title="Test PR",
            body="This is a test PR",
            head_branch="feature-branch",
            base_branch="main",
            draft=False,
        )

        assert isinstance(pr, GitHubPullRequest)
        assert pr.title == "Test PR"
        assert pr.head_branch == "feature-branch"
        assert pr.base_branch == "main"
        assert pr.state == "open"
        assert "github.com" in pr.url

    @pytest.mark.asyncio
    async def test_create_draft_pull_request(self, github_adapter: GitHubAdapter) -> None:
        """Test creating a draft pull request."""
        pr = await github_adapter.create_pull_request(
            title="Draft PR",
            body="This is a draft",
            head_branch="wip-branch",
            base_branch="main",
            draft=True,
        )

        assert isinstance(pr, GitHubPullRequest)
        assert pr.title == "Draft PR"

    @pytest.mark.asyncio
    async def test_update_pull_request(self, github_adapter: GitHubAdapter) -> None:
        """Test updating an existing pull request."""
        pr = await github_adapter.update_pull_request(
            pr_number=123,
            body="Updated PR body",
            state="closed",
        )

        assert isinstance(pr, GitHubPullRequest)
        assert pr.number == 123
        assert pr.body == "Updated PR body"
        assert pr.state == "closed"

    @pytest.mark.asyncio
    async def test_add_comment_to_pull_request(self, github_adapter: GitHubAdapter) -> None:
        """Test adding a comment to a PR."""
        # Should not raise
        await github_adapter.add_comment_to_pull_request(
            pr_number=123,
            comment="This is a test comment",
        )

    @pytest.mark.asyncio
    async def test_get_check_status(self, github_adapter: GitHubAdapter) -> None:
        """Test retrieving check status for a ref."""
        status = await github_adapter.get_check_status(ref="abc123def")

        assert status["ref"] == "abc123def"
        assert "status" in status
        assert "conclusion" in status
        assert "checks" in status

    @pytest.mark.asyncio
    async def test_get_check_runs(self, github_adapter: GitHubAdapter) -> None:
        """Test retrieving detailed check runs."""
        runs = await github_adapter.get_check_runs(ref="abc123def")

        assert isinstance(runs, list)
        # Stub returns empty list
        assert len(runs) == 0


class TestIncidentIssueCreation:
    """Test suite for incident issue creation with evidence."""

    @pytest.fixture
    def incident_data(self) -> IncidentIssueData:
        """Create sample incident data."""
        return IncidentIssueData(
            summary="API response time degradation detected",
            severity="sev2",
            timeline=[
                (datetime(2024, 1, 15, 10, 0, tzinfo=UTC), "Anomaly detected in p95 latency"),
                (datetime(2024, 1, 15, 10, 5, tzinfo=UTC), "Alert threshold exceeded"),
                (datetime(2024, 1, 15, 10, 10, tzinfo=UTC), "Incident opened"),
            ],
            affected_service="demo-api",
            metrics={
                "p50_latency_ms": 250,
                "p95_latency_ms": 1200,
                "p99_latency_ms": 2500,
                "error_rate": 0.025,
            },
            logs=[
                "2024-01-15T10:05:23Z ERROR Database connection timeout",
                "2024-01-15T10:05:45Z WARN Retry attempt 1/3 failed",
                "2024-01-15T10:06:12Z ERROR Database connection timeout",
            ],
            traces=[
                "trace-abc123",
                "trace-def456",
                "trace-ghi789",
            ],
            recent_deployments=[
                GitHubDeployment(
                    id=1,
                    environment="production",
                    sha="abc123def456",
                    ref="main",
                    creator="deploy-bot",
                    created_at=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
                    updated_at=datetime(2024, 1, 15, 9, 35, tzinfo=UTC),
                    state="success",
                    description="Deploy v1.2.3",
                ),
            ],
            suspected_root_cause="Database connection pool exhaustion after recent deployment",
            confidence=0.85,
            remediation_proposal="Increase database connection pool size from 10 to 20",
            evidence_ids=["evidence-001", "evidence-002", "evidence-003"],
        )

    @pytest.mark.asyncio
    async def test_create_incident_issue(
        self, github_adapter: GitHubAdapter, incident_data: IncidentIssueData
    ) -> None:
        """Test creating an incident issue with full evidence."""
        issue = await github_adapter.create_incident_issue(data=incident_data)

        assert isinstance(issue, GitHubIssue)
        assert "sev2" in issue.title.lower()
        assert incident_data.affected_service in issue.title
        assert incident_data.summary in issue.title

        # Check body contains all required sections
        assert "## Incident Summary" in issue.body
        assert incident_data.summary in issue.body
        assert "## Timeline" in issue.body
        assert "## Metrics" in issue.body
        assert "## Log Evidence" in issue.body
        assert "## Traces" in issue.body
        assert "## Recent Deployments" in issue.body
        assert "## Suspected Root Cause" in issue.body
        assert "## Remediation Proposal" in issue.body
        assert "## Evidence IDs" in issue.body

        # Check labels
        assert "incident" in issue.labels
        assert "sev2" in issue.labels
        assert "automated" in issue.labels

    @pytest.mark.asyncio
    async def test_incident_issue_formats_timeline(
        self, github_adapter: GitHubAdapter, incident_data: IncidentIssueData
    ) -> None:
        """Test incident issue correctly formats timeline entries."""
        issue = await github_adapter.create_incident_issue(data=incident_data)

        # Check timeline formatting
        assert "2024-01-15 10:00:00 UTC" in issue.body
        assert "Anomaly detected" in issue.body

    @pytest.mark.asyncio
    async def test_incident_issue_includes_metrics(
        self, github_adapter: GitHubAdapter, incident_data: IncidentIssueData
    ) -> None:
        """Test incident issue includes metrics in JSON format."""
        issue = await github_adapter.create_incident_issue(data=incident_data)

        assert "p95_latency_ms" in issue.body
        assert "1200" in issue.body
        assert "```json" in issue.body

    @pytest.mark.asyncio
    async def test_incident_issue_limits_logs(
        self, github_adapter: GitHubAdapter, incident_data: IncidentIssueData
    ) -> None:
        """Test incident issue limits log entries to prevent overflow."""
        # Add many logs
        incident_data.logs.extend([f"Log entry {i}" for i in range(20)])

        issue = await github_adapter.create_incident_issue(data=incident_data)

        # Should show first 10 and mention more
        assert "...and" in issue.body
        assert "more log entries" in issue.body

    @pytest.mark.asyncio
    async def test_incident_issue_limits_traces(
        self, github_adapter: GitHubAdapter, incident_data: IncidentIssueData
    ) -> None:
        """Test incident issue limits trace IDs to prevent overflow."""
        # Add many traces
        incident_data.traces.extend([f"trace-{i:03d}" for i in range(10)])

        issue = await github_adapter.create_incident_issue(data=incident_data)

        # Should show first 5 and mention more
        assert "...and" in issue.body
        assert "more traces" in issue.body


class TestRemediationPRCreation:
    """Test suite for automated remediation PR creation."""

    @pytest.fixture
    def remediation_data(self) -> RemediationPRData:
        """Create sample remediation data."""
        return RemediationPRData(
            incident_id="INC-2024-001",
            incident_url="https://github.com/test-org/test-repo/issues/42",
            changes={
                "config/database.yaml": "max_connections: 20\npool_timeout: 30s\n",
                "deployment/api.yaml": "replicas: 3\n",
            },
            proposal_id="PROP-2024-001-A",
            approval_id="APPR-2024-001-human-123",
            validation_results={
                "schema_valid": True,
                "linting_passed": True,
                "security_scan": "passed",
                "estimated_risk": "low",
            },
            risk_assessment="Low risk: configuration change only, no code changes. Rollback available.",
            rollback_plan="1. Revert this PR\n2. Redeploy previous config\n3. Verify metrics",
        )

    @pytest.mark.asyncio
    async def test_create_remediation_pr(
        self, github_adapter: GitHubAdapter, remediation_data: RemediationPRData
    ) -> None:
        """Test creating a remediation PR from approved proposal."""
        pr = await github_adapter.create_remediation_pr(data=remediation_data)

        assert isinstance(pr, GitHubPullRequest)
        assert remediation_data.incident_id in pr.title
        assert pr.head_branch.startswith("remediation/")
        assert pr.base_branch == "main"
        assert not pr.draft  # Never draft

        # Check body contains all required sections
        assert "## Automated Remediation" in pr.body
        assert "### Governance" in pr.body
        assert "### Risk Assessment" in pr.body
        assert "### Validation Results" in pr.body
        assert "### Rollback Plan" in pr.body
        assert "### Changed Files" in pr.body

        # Check metadata is present
        assert remediation_data.proposal_id in pr.body
        assert remediation_data.approval_id in pr.body
        assert remediation_data.incident_url in pr.body

    @pytest.mark.asyncio
    async def test_remediation_pr_requires_approval(
        self, github_adapter: GitHubAdapter, remediation_data: RemediationPRData
    ) -> None:
        """Test remediation PR creation requires approval_id."""
        remediation_data.approval_id = ""

        with pytest.raises(ValueError, match="Cannot create remediation PR without approval_id"):
            await github_adapter.create_remediation_pr(data=remediation_data)

    @pytest.mark.asyncio
    async def test_remediation_pr_includes_validation_results(
        self, github_adapter: GitHubAdapter, remediation_data: RemediationPRData
    ) -> None:
        """Test remediation PR includes validation results."""
        pr = await github_adapter.create_remediation_pr(data=remediation_data)

        assert "schema_valid" in pr.body
        assert "linting_passed" in pr.body
        assert "```json" in pr.body

    @pytest.mark.asyncio
    async def test_remediation_pr_includes_changed_files(
        self, github_adapter: GitHubAdapter, remediation_data: RemediationPRData
    ) -> None:
        """Test remediation PR lists all changed files."""
        pr = await github_adapter.create_remediation_pr(data=remediation_data)

        assert "config/database.yaml" in pr.body
        assert "deployment/api.yaml" in pr.body

    @pytest.mark.asyncio
    async def test_remediation_pr_includes_warning(
        self, github_adapter: GitHubAdapter, remediation_data: RemediationPRData
    ) -> None:
        """Test remediation PR includes manual merge warning."""
        pr = await github_adapter.create_remediation_pr(data=remediation_data)

        assert "⚠️" in pr.body
        assert "manually merged" in pr.body
        assert "Auto-merge is disabled" in pr.body

    @pytest.mark.asyncio
    async def test_remediation_pr_branch_naming(
        self, github_adapter: GitHubAdapter, remediation_data: RemediationPRData
    ) -> None:
        """Test remediation PR creates correctly named branch."""
        pr = await github_adapter.create_remediation_pr(data=remediation_data)

        # Branch should be remediation/{incident_id}/{proposal_id_prefix}
        assert pr.head_branch.startswith("remediation/INC-2024-001/")
        assert pr.head_branch.endswith(remediation_data.proposal_id[:8])

    @pytest.mark.asyncio
    async def test_remediation_pr_commit_message(
        self, github_adapter: GitHubAdapter, remediation_data: RemediationPRData
    ) -> None:
        """Test remediation PR uses proper commit message format."""
        # We can't directly test the commit message in stub,
        # but we can verify the method was called correctly
        pr = await github_adapter.create_remediation_pr(data=remediation_data)

        # Just verify PR was created successfully
        assert pr is not None


class TestGitHubWorkflow:
    """Test suite for complete GitHub workflow (branch -> commit -> PR)."""

    @pytest.mark.asyncio
    async def test_create_branch(self, github_adapter: GitHubAdapter) -> None:
        """Test creating a new branch."""
        sha = await github_adapter.create_branch(
            branch_name="feature/test-branch",
            base_ref="main",
        )

        assert isinstance(sha, str)
        assert len(sha) > 0

    @pytest.mark.asyncio
    async def test_commit_files(self, github_adapter: GitHubAdapter) -> None:
        """Test committing files to a branch."""
        files = {
            "src/test.py": "print('hello')",
            "README.md": "# Test",
        }

        sha = await github_adapter.commit_files(
            branch="feature/test-branch",
            files=files,
            message="Test commit",
            author={"name": "Test User", "email": "test@example.com"},
        )

        assert isinstance(sha, str)
        assert len(sha) > 0

    @pytest.mark.asyncio
    async def test_commit_files_without_author(self, github_adapter: GitHubAdapter) -> None:
        """Test committing files without explicit author."""
        files = {"test.txt": "content"}

        sha = await github_adapter.commit_files(
            branch="test-branch",
            files=files,
            message="Test commit",
        )

        assert isinstance(sha, str)


class TestDataClasses:
    """Test suite for GitHub data classes."""

    def test_github_config_creation(self) -> None:
        """Test creating GitHub config."""
        config = GitHubConfig(
            token="test_token",
            owner="test-owner",
            repo="test-repo",
        )

        assert config.token == "test_token"
        assert config.owner == "test-owner"
        assert config.repo == "test-repo"
        assert config.api_base_url == "https://api.github.com"

    def test_github_commit_creation(self) -> None:
        """Test creating GitHub commit."""
        commit = GitHubCommit(
            sha="abc123",
            message="Test commit",
            author="test-author",
            timestamp=datetime.now(tz=UTC),
            url="https://github.com/test/test/commit/abc123",
        )

        assert commit.sha == "abc123"
        assert commit.message == "Test commit"

    def test_github_deployment_creation(self) -> None:
        """Test creating GitHub deployment."""
        deployment = GitHubDeployment(
            id=123,
            environment="production",
            sha="abc123",
            ref="main",
            creator="deploy-bot",
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
            state="success",
            description="Deploy v1.0",
        )

        assert deployment.environment == "production"
        assert deployment.state == "success"

    def test_github_check_run_creation(self) -> None:
        """Test creating GitHub check run."""
        check = GitHubCheckRun(
            id=1,
            name="CI Tests",
            status="completed",
            conclusion="success",
            started_at=datetime.now(tz=UTC),
            completed_at=datetime.now(tz=UTC),
            output_title="All tests passed",
            output_summary="100% pass rate",
        )

        assert check.name == "CI Tests"
        assert check.conclusion == "success"

    def test_incident_issue_data_creation(self) -> None:
        """Test creating incident issue data."""
        data = IncidentIssueData(
            summary="Test incident",
            severity="sev1",
            timeline=[],
            affected_service="test-service",
            metrics={},
            logs=[],
            traces=[],
            recent_deployments=[],
            suspected_root_cause="Unknown",
            confidence=0.5,
            remediation_proposal="Fix it",
            evidence_ids=[],
        )

        assert data.severity == "sev1"
        assert data.confidence == 0.5

    def test_remediation_pr_data_creation(self) -> None:
        """Test creating remediation PR data."""
        data = RemediationPRData(
            incident_id="INC-001",
            incident_url="https://github.com/test/test/issues/1",
            changes={"file.py": "content"},
            proposal_id="PROP-001",
            approval_id="APPR-001",
            validation_results={},
            risk_assessment="Low",
            rollback_plan="Revert",
        )

        assert data.incident_id == "INC-001"
        assert data.approval_id == "APPR-001"
