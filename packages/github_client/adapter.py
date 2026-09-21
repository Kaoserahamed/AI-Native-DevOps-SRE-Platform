"""GitHub adapter for repository operations, issues, and PRs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GitHubConfig:
    """Configuration for GitHub API access."""

    token: str | None = None
    owner: str = ""
    repo: str = ""
    api_base_url: str = "https://api.github.com"


@dataclass
class GitHubCommit:
    """A single commit from GitHub."""

    sha: str
    message: str
    author: str
    timestamp: datetime
    url: str


@dataclass
class GitHubDeployment:
    """A deployment event from GitHub."""

    id: int
    environment: str
    sha: str
    ref: str
    creator: str
    created_at: datetime
    updated_at: datetime
    state: str  # success, failure, pending, etc.
    description: str


@dataclass
class GitHubIssue:
    """A GitHub issue."""

    number: int
    title: str
    body: str
    state: str
    url: str
    created_at: datetime
    labels: list[str]


@dataclass
class GitHubPullRequest:
    """A GitHub pull request."""

    number: int
    title: str
    body: str
    state: str
    head_branch: str
    base_branch: str
    url: str
    created_at: datetime
    draft: bool = False
    mergeable: bool | None = None


@dataclass
class GitHubCheckRun:
    """A check run from GitHub Checks API."""

    id: int
    name: str
    status: str  # queued, in_progress, completed
    conclusion: (
        str | None
    )  # success, failure, neutral, cancelled, skipped, timed_out, action_required
    started_at: datetime | None
    completed_at: datetime | None
    output_title: str | None
    output_summary: str | None


@dataclass
class IncidentIssueData:
    """Data for creating an incident issue with evidence."""

    summary: str
    severity: str
    timeline: list[tuple[datetime, str]]  # timestamp, event description
    affected_service: str
    metrics: dict[str, Any]
    logs: list[str]
    traces: list[str]
    recent_deployments: list[GitHubDeployment]
    suspected_root_cause: str
    confidence: float
    remediation_proposal: str
    evidence_ids: list[str]


@dataclass
class RemediationPRData:
    """Data for creating a remediation pull request."""

    incident_id: str
    incident_url: str
    changes: dict[str, str]  # filename -> content
    proposal_id: str
    approval_id: str
    validation_results: dict[str, Any]
    risk_assessment: str
    rollback_plan: str


class GitHubAdapter:
    """Adapter for GitHub API operations with least-privilege permissions."""

    def __init__(self, config: GitHubConfig) -> None:
        """Initialize GitHub adapter.

        Parameters
        ----------
        config
            GitHub configuration with token and repository details
        """
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate configuration is complete."""
        if not self.config.owner:
            raise ValueError("GitHub owner is required")
        if not self.config.repo:
            raise ValueError("GitHub repo is required")

    async def get_repository_metadata(self) -> dict[str, Any]:
        """Retrieve repository metadata.

        Returns
        -------
        dict[str, Any]
            Repository information
        """
        logger.info("Fetching repository metadata for %s/%s", self.config.owner, self.config.repo)

        # Stub implementation - would call GitHub API
        return {
            "owner": self.config.owner,
            "repo": self.config.repo,
            "default_branch": "main",
            "private": False,
        }

    async def get_commit_history(
        self, since: datetime | None = None, until: datetime | None = None, limit: int = 100
    ) -> list[GitHubCommit]:
        """Retrieve commit history within time range.

        Parameters
        ----------
        since
            Start time for commits
        until
            End time for commits
        limit
            Maximum number of commits to retrieve

        Returns
        -------
        list[GitHubCommit]
            Commit history
        """
        logger.info(
            "Fetching commit history for %s/%s (limit: %d)",
            self.config.owner,
            self.config.repo,
            limit,
        )

        # Stub - would call GitHub API
        return []

    async def get_deployment_history(
        self, environment: str = "production", limit: int = 20
    ) -> list[GitHubDeployment]:
        """Retrieve deployment history for an environment.

        Parameters
        ----------
        environment
            Environment name
        limit
            Maximum number of deployments

        Returns
        -------
        list[GitHubDeployment]
            Deployment records
        """
        logger.info(
            "Fetching deployment history for %s/%s environment %s",
            self.config.owner,
            self.config.repo,
            environment,
        )

        # Stub - would call GitHub Deployments API
        # GET /repos/{owner}/{repo}/deployments?environment={environment}&per_page={limit}
        return []

    async def create_issue(
        self, title: str, body: str, labels: list[str] | None = None
    ) -> GitHubIssue:
        """Create a GitHub issue.

        Parameters
        ----------
        title
            Issue title
        body
            Issue body (Markdown)
        labels
            Optional labels to apply

        Returns
        -------
        GitHubIssue
            Created issue
        """
        labels = labels or []
        logger.info(
            "Creating issue '%s' with labels %s in %s/%s",
            title,
            labels,
            self.config.owner,
            self.config.repo,
        )

        # Stub - would POST to /repos/{owner}/{repo}/issues
        return GitHubIssue(
            number=1,
            title=title,
            body=body,
            state="open",
            url=f"https://github.com/{self.config.owner}/{self.config.repo}/issues/1",
            created_at=datetime.now(),
            labels=labels,
        )

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
        draft: bool = False,
    ) -> GitHubPullRequest:
        """Create a pull request.

        Parameters
        ----------
        title
            PR title
        body
            PR description (Markdown)
        head_branch
            Source branch with changes
        base_branch
            Target branch (default: main)
        draft
            Create as draft PR

        Returns
        -------
        GitHubPullRequest
            Created pull request
        """
        logger.info(
            "Creating PR '%s' from %s to %s in %s/%s",
            title,
            head_branch,
            base_branch,
            self.config.owner,
            self.config.repo,
        )

        # Stub - would POST to /repos/{owner}/{repo}/pulls
        return GitHubPullRequest(
            number=1,
            title=title,
            body=body,
            state="open",
            head_branch=head_branch,
            base_branch=base_branch,
            url=f"https://github.com/{self.config.owner}/{self.config.repo}/pull/1",
            created_at=datetime.now(),
        )

    async def update_pull_request(
        self, pr_number: int, body: str | None = None, state: str | None = None
    ) -> GitHubPullRequest:
        """Update an existing pull request.

        Parameters
        ----------
        pr_number
            PR number to update
        body
            New PR body (optional)
        state
            New state: open or closed (optional)

        Returns
        -------
        GitHubPullRequest
            Updated pull request
        """
        logger.info("Updating PR #%d in %s/%s", pr_number, self.config.owner, self.config.repo)

        # Stub - would PATCH to /repos/{owner}/{repo}/pulls/{pr_number}
        return GitHubPullRequest(
            number=pr_number,
            title="Updated PR",
            body=body or "Updated",
            state=state or "open",
            head_branch="feature-branch",
            base_branch="main",
            url=f"https://github.com/{self.config.owner}/{self.config.repo}/pull/{pr_number}",
            created_at=datetime.now(),
        )

    async def add_comment_to_pull_request(self, pr_number: int, comment: str) -> None:
        """Add a comment to an existing pull request.

        Parameters
        ----------
        pr_number
            PR number
        comment
            Comment text (Markdown)
        """
        logger.info(
            "Adding comment to PR #%d in %s/%s", pr_number, self.config.owner, self.config.repo
        )

        # Stub - would POST to /repos/{owner}/{repo}/issues/{pr_number}/comments

    async def get_check_status(self, ref: str) -> dict[str, Any]:
        """Get CI check status for a git ref.

        Parameters
        ----------
        ref
            Git ref (commit SHA, branch, or tag)

        Returns
        -------
        dict[str, Any]
            Check status information with summary and detailed checks
        """
        logger.info(
            "Fetching check status for %s in %s/%s", ref, self.config.owner, self.config.repo
        )

        # Stub - would call GitHub Checks API
        # GET /repos/{owner}/{repo}/commits/{ref}/check-runs
        return {
            "ref": ref,
            "status": "completed",
            "conclusion": "success",
            "checks": [],
        }

    async def get_check_runs(self, ref: str) -> list[GitHubCheckRun]:
        """Get detailed check runs for a git ref.

        Parameters
        ----------
        ref
            Git ref (commit SHA, branch, or tag)

        Returns
        -------
        list[GitHubCheckRun]
            Detailed check run information
        """
        logger.info("Fetching check runs for %s in %s/%s", ref, self.config.owner, self.config.repo)

        # Stub - would call GitHub Checks API
        # GET /repos/{owner}/{repo}/commits/{ref}/check-runs
        return []

    async def create_incident_issue(self, data: IncidentIssueData) -> GitHubIssue:
        """Create a GitHub issue for an incident with full evidence and context.

        Parameters
        ----------
        data
            Incident data including summary, timeline, metrics, logs, traces

        Returns
        -------
        GitHubIssue
            Created incident issue
        """
        logger.info(
            "Creating incident issue for %s (severity: %s) in %s/%s",
            data.affected_service,
            data.severity,
            self.config.owner,
            self.config.repo,
        )

        # Format the issue body with all evidence
        body_sections = [
            "## Incident Summary",
            data.summary,
            "",
            f"**Severity:** {data.severity}",
            f"**Affected Service:** {data.affected_service}",
            f"**Confidence:** {data.confidence:.2%}",
            "",
            "## Timeline",
        ]

        for timestamp, event in data.timeline:
            body_sections.append(f"- **{timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}**: {event}")

        body_sections.extend(
            [
                "",
                "## Metrics",
                "```json",
            ]
        )
        import json

        body_sections.append(json.dumps(data.metrics, indent=2))
        body_sections.extend(
            [
                "```",
                "",
                "## Log Evidence",
            ]
        )

        for i, log_line in enumerate(data.logs[:10], 1):  # Limit to 10 log lines
            body_sections.append(f"{i}. `{log_line}`")

        if len(data.logs) > 10:
            body_sections.append(f"\n*...and {len(data.logs) - 10} more log entries*")

        body_sections.extend(
            [
                "",
                "## Traces",
            ]
        )

        for trace_id in data.traces[:5]:  # Limit to 5 trace IDs
            body_sections.append(f"- `{trace_id}`")

        if len(data.traces) > 5:
            body_sections.append(f"\n*...and {len(data.traces) - 5} more traces*")

        body_sections.extend(
            [
                "",
                "## Recent Deployments",
            ]
        )

        for deployment in data.recent_deployments[:5]:
            body_sections.append(
                f"- **{deployment.created_at.strftime('%Y-%m-%d %H:%M:%S')}**: "
                f"{deployment.environment} - {deployment.sha[:7]} ({deployment.state})"
            )

        body_sections.extend(
            [
                "",
                "## Suspected Root Cause",
                data.suspected_root_cause,
                "",
                "## Remediation Proposal",
                data.remediation_proposal,
                "",
                "## Evidence IDs",
            ]
        )

        for evidence_id in data.evidence_ids:
            body_sections.append(f"- `{evidence_id}`")

        body = "\n".join(body_sections)

        title = f"[{data.severity.upper()}] {data.affected_service}: {data.summary[:100]}"

        labels = ["incident", data.severity.lower(), "automated"]

        return await self.create_issue(title=title, body=body, labels=labels)

    async def create_branch(self, branch_name: str, base_ref: str = "main") -> str:
        """Create a new branch from a base ref.

        Parameters
        ----------
        branch_name
            Name of the new branch
        base_ref
            Base branch or commit SHA

        Returns
        -------
        str
            SHA of the new branch's head commit
        """
        logger.info(
            "Creating branch %s from %s in %s/%s",
            branch_name,
            base_ref,
            self.config.owner,
            self.config.repo,
        )

        # Stub - would:
        # 1. GET /repos/{owner}/{repo}/git/ref/heads/{base_ref} to get SHA
        # 2. POST /repos/{owner}/{repo}/git/refs to create new branch
        return "abc123"

    async def commit_files(
        self, branch: str, files: dict[str, str], message: str, author: dict[str, str] | None = None
    ) -> str:
        """Commit file changes to a branch.

        Parameters
        ----------
        branch
            Target branch name
        files
            Dictionary of filepath -> content
        message
            Commit message
        author
            Optional author info: {"name": "...", "email": "..."}

        Returns
        -------
        str
            SHA of the new commit
        """
        logger.info(
            "Committing %d files to %s in %s/%s",
            len(files),
            branch,
            self.config.owner,
            self.config.repo,
        )

        # Stub - would:
        # For each file:
        #   1. GET /repos/{owner}/{repo}/contents/{path}?ref={branch} (if updating)
        #   2. PUT /repos/{owner}/{repo}/contents/{path} with content and message
        # Or use Git Data API for atomic multi-file commits:
        #   1. GET tree SHA for branch
        #   2. Create blobs for each file
        #   3. Create new tree with updated blobs
        #   4. Create commit pointing to new tree
        #   5. Update branch ref
        return "def456"

    async def create_remediation_pr(self, data: RemediationPRData) -> GitHubPullRequest:
        """Create a governed remediation pull request from an approved proposal.

        This method enforces the policy that only approved proposals can become PRs,
        and all PRs are tagged with machine-readable metadata for audit trail.

        Parameters
        ----------
        data
            Remediation PR data with incident context, changes, and validation

        Returns
        -------
        GitHubPullRequest
            Created pull request

        Raises
        ------
        ValueError
            If approval_id is missing (only approved proposals can create PRs)
        """
        if not data.approval_id:
            raise ValueError("Cannot create remediation PR without approval_id")

        logger.info(
            "Creating remediation PR for incident %s (proposal: %s, approval: %s) in %s/%s",
            data.incident_id,
            data.proposal_id,
            data.approval_id,
            self.config.owner,
            self.config.repo,
        )

        # Create branch for remediation
        branch_name = f"remediation/{data.incident_id}/{data.proposal_id[:8]}"
        await self.create_branch(branch_name=branch_name, base_ref="main")

        # Commit changes
        commit_message = f"fix: remediation for incident {data.incident_id}\n\nProposal: {data.proposal_id}\nApproval: {data.approval_id}"
        await self.commit_files(
            branch=branch_name,
            files=data.changes,
            message=commit_message,
            author={"name": "AI SRE Agent", "email": "sre-agent@platform.local"},
        )

        # Format PR body with complete metadata
        body_sections = [
            "## Automated Remediation",
            f"This PR implements an approved remediation for incident [{data.incident_id}]({data.incident_url}).",
            "",
            "### Governance",
            f"- **Proposal ID:** `{data.proposal_id}`",
            f"- **Approval ID:** `{data.approval_id}`",
            f"- **Incident:** {data.incident_url}",
            "",
            "### Risk Assessment",
            data.risk_assessment,
            "",
            "### Validation Results",
            "```json",
        ]

        import json

        body_sections.append(json.dumps(data.validation_results, indent=2))
        body_sections.extend(
            [
                "```",
                "",
                "### Rollback Plan",
                data.rollback_plan,
                "",
                "### Changed Files",
            ]
        )

        for filepath in data.changes.keys():
            body_sections.append(f"- `{filepath}`")

        body_sections.extend(
            [
                "",
                "---",
                "",
                "**⚠️ Important:** This PR must be reviewed and manually merged. Auto-merge is disabled for production-changing PRs.",
                "",
                f"**Metadata:** `incident:{data.incident_id}` `proposal:{data.proposal_id}` `approval:{data.approval_id}`",
            ]
        )

        body = "\n".join(body_sections)

        title = f"fix: remediation for incident {data.incident_id}"

        # Create the PR (never as draft, always requires review)
        pr = await self.create_pull_request(
            title=title,
            body=body,
            head_branch=branch_name,
            base_branch="main",
            draft=False,
        )

        logger.info(
            "Created remediation PR #%d for incident %s: %s",
            pr.number,
            data.incident_id,
            pr.url,
        )

        return pr
