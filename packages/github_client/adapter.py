"""GitHub adapter for repository operations, issues, and PRs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

import httpx

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
        self._client: httpx.AsyncClient | None = None

    def _validate_config(self) -> None:
        """Validate configuration is complete."""
        if not self.config.owner:
            raise ValueError("GitHub owner is required")
        if not self.config.repo:
            raise ValueError("GitHub repo is required")

    def _get_headers(self) -> dict[str, str]:
        """Build headers for GitHub API requests."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.api_base_url,
                headers=self._get_headers(),
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> GitHubAdapter:
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        await self.close()

    async def get_repository_metadata(self) -> dict[str, Any]:
        """Retrieve repository metadata.

        Returns
        -------
        dict[str, Any]
            Repository information
        """
        logger.info("Fetching repository metadata for %s/%s", self.config.owner, self.config.repo)

        client = await self._get_client()
        response = await client.get(f"/repos/{self.config.owner}/{self.config.repo}")
        response.raise_for_status()

        data = response.json()
        return {
            "owner": data["owner"]["login"],
            "repo": data["name"],
            "default_branch": data["default_branch"],
            "private": data["private"],
            "description": data.get("description"),
            "language": data.get("language"),
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
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

        client = await self._get_client()
        params: dict[str, Any] = {"per_page": min(limit, 100)}

        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()

        response = await client.get(
            f"/repos/{self.config.owner}/{self.config.repo}/commits", params=params
        )
        response.raise_for_status()

        commits_data = response.json()
        commits = []

        for commit_data in commits_data:
            try:
                commits.append(
                    GitHubCommit(
                        sha=commit_data["sha"],
                        message=commit_data["commit"]["message"],
                        author=commit_data["commit"]["author"]["name"],
                        timestamp=datetime.fromisoformat(
                            commit_data["commit"]["author"]["date"].replace("Z", "+00:00")
                        ),
                        url=commit_data["html_url"],
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning(
                    "Failed to parse commit %s: %s", commit_data.get("sha", "unknown"), e
                )
                continue

        logger.info("Retrieved %d commits", len(commits))
        return commits

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

        client = await self._get_client()
        params: dict[str, str | int] = {
            "environment": environment,
            "per_page": min(limit, 100),
        }

        response = await client.get(
            f"/repos/{self.config.owner}/{self.config.repo}/deployments", params=params
        )
        response.raise_for_status()

        deployments_data = response.json()
        deployments = []

        for dep_data in deployments_data:
            try:
                deployments.append(
                    GitHubDeployment(
                        id=dep_data["id"],
                        environment=dep_data["environment"],
                        sha=dep_data["sha"],
                        ref=dep_data["ref"],
                        creator=dep_data["creator"]["login"],
                        created_at=datetime.fromisoformat(
                            dep_data["created_at"].replace("Z", "+00:00")
                        ),
                        updated_at=datetime.fromisoformat(
                            dep_data["updated_at"].replace("Z", "+00:00")
                        ),
                        state=dep_data.get("statuses_url", "unknown"),  # Would need separate call
                        description=dep_data.get("description", ""),
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning(
                    "Failed to parse deployment %s: %s", dep_data.get("id", "unknown"), e
                )
                continue

        logger.info("Retrieved %d deployments for %s", len(deployments), environment)
        return deployments

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

        client = await self._get_client()
        payload = {"title": title, "body": body, "labels": labels}

        response = await client.post(
            f"/repos/{self.config.owner}/{self.config.repo}/issues", json=payload
        )
        response.raise_for_status()

        issue_data = response.json()
        issue = GitHubIssue(
            number=issue_data["number"],
            title=issue_data["title"],
            body=issue_data["body"],
            state=issue_data["state"],
            url=issue_data["html_url"],
            created_at=datetime.fromisoformat(issue_data["created_at"].replace("Z", "+00:00")),
            labels=[label["name"] for label in issue_data.get("labels", [])],
        )

        logger.info("Created issue #%d: %s", issue.number, issue.url)
        return issue

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

        client = await self._get_client()
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
            "draft": draft,
        }

        response = await client.post(
            f"/repos/{self.config.owner}/{self.config.repo}/pulls", json=payload
        )
        response.raise_for_status()

        pr_data = response.json()
        pr = GitHubPullRequest(
            number=pr_data["number"],
            title=pr_data["title"],
            body=pr_data["body"],
            state=pr_data["state"],
            head_branch=pr_data["head"]["ref"],
            base_branch=pr_data["base"]["ref"],
            url=pr_data["html_url"],
            created_at=datetime.fromisoformat(pr_data["created_at"].replace("Z", "+00:00")),
            draft=pr_data.get("draft", False),
            mergeable=pr_data.get("mergeable"),
        )

        logger.info("Created PR #%d: %s", pr.number, pr.url)
        return pr

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

        client = await self._get_client()
        payload = {}
        if body is not None:
            payload["body"] = body
        if state is not None:
            payload["state"] = state

        response = await client.patch(
            f"/repos/{self.config.owner}/{self.config.repo}/pulls/{pr_number}", json=payload
        )
        response.raise_for_status()

        pr_data = response.json()
        pr = GitHubPullRequest(
            number=pr_data["number"],
            title=pr_data["title"],
            body=pr_data["body"],
            state=pr_data["state"],
            head_branch=pr_data["head"]["ref"],
            base_branch=pr_data["base"]["ref"],
            url=pr_data["html_url"],
            created_at=datetime.fromisoformat(pr_data["created_at"].replace("Z", "+00:00")),
            draft=pr_data.get("draft", False),
            mergeable=pr_data.get("mergeable"),
        )

        logger.info("Updated PR #%d: %s", pr.number, pr.url)
        return pr

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

        client = await self._get_client()
        payload = {"body": comment}

        response = await client.post(
            f"/repos/{self.config.owner}/{self.config.repo}/issues/{pr_number}/comments",
            json=payload,
        )
        response.raise_for_status()

        logger.info("Added comment to PR #%d", pr_number)

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

        check_runs = await self.get_check_runs(ref)

        # Aggregate status and conclusion
        if not check_runs:
            return {
                "ref": ref,
                "status": "completed",
                "conclusion": "success",
                "checks": [],
            }

        all_completed = all(run.status == "completed" for run in check_runs)
        any_failures = any(
            run.conclusion in ["failure", "timed_out", "action_required"] for run in check_runs
        )

        status = "completed" if all_completed else "in_progress"
        conclusion = "failure" if any_failures else "success" if all_completed else "pending"

        return {
            "ref": ref,
            "status": status,
            "conclusion": conclusion,
            "checks": [
                {
                    "name": run.name,
                    "status": run.status,
                    "conclusion": run.conclusion,
                }
                for run in check_runs
            ],
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

        client = await self._get_client()
        response = await client.get(
            f"/repos/{self.config.owner}/{self.config.repo}/commits/{ref}/check-runs"
        )
        response.raise_for_status()

        data = response.json()
        check_runs = []

        for run in data.get("check_runs", []):
            try:
                check_runs.append(
                    GitHubCheckRun(
                        id=run["id"],
                        name=run["name"],
                        status=run["status"],
                        conclusion=run.get("conclusion"),
                        started_at=(
                            datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
                            if run.get("started_at")
                            else None
                        ),
                        completed_at=(
                            datetime.fromisoformat(run["completed_at"].replace("Z", "+00:00"))
                            if run.get("completed_at")
                            else None
                        ),
                        output_title=run.get("output", {}).get("title"),
                        output_summary=run.get("output", {}).get("summary"),
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning("Failed to parse check run %s: %s", run.get("id", "unknown"), e)
                continue

        logger.info("Retrieved %d check runs for %s", len(check_runs), ref)
        return check_runs

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

        # Limit to 5 trace IDs
        body_sections.extend(f"- `{trace_id}`" for trace_id in data.traces[:5])

        if len(data.traces) > 5:
            body_sections.append(f"\n*...and {len(data.traces) - 5} more traces*")

        body_sections.extend(
            [
                "",
                "## Recent Deployments",
            ]
        )

        body_sections.extend(
            f"- **{deployment.created_at.strftime('%Y-%m-%d %H:%M:%S')}**: "
            f"{deployment.environment} - {deployment.sha[:7]} ({deployment.state})"
            for deployment in data.recent_deployments[:5]
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

        body_sections.extend(f"- `{evidence_id}`" for evidence_id in data.evidence_ids)

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

        client = await self._get_client()

        # Get SHA of the base ref
        try:
            ref_response = await client.get(
                f"/repos/{self.config.owner}/{self.config.repo}/git/ref/heads/{base_ref}"
            )
            ref_response.raise_for_status()
            base_sha = ref_response.json()["object"]["sha"]
        except httpx.HTTPStatusError:
            # Try as a direct commit SHA
            commit_response = await client.get(
                f"/repos/{self.config.owner}/{self.config.repo}/git/commits/{base_ref}"
            )
            commit_response.raise_for_status()
            base_sha = commit_response.json()["sha"]

        # Create the new branch
        payload = {"ref": f"refs/heads/{branch_name}", "sha": base_sha}

        response = await client.post(
            f"/repos/{self.config.owner}/{self.config.repo}/git/refs", json=payload
        )
        response.raise_for_status()

        created_sha: str = response.json()["object"]["sha"]
        logger.info("Created branch %s at SHA %s", branch_name, created_sha)
        return created_sha

    async def commit_files(
        self, branch: str, files: dict[str, str], message: str, author: dict[str, str] | None = None
    ) -> str:
        """Commit file changes to a branch using Git Data API for atomic multi-file commits.

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

        client = await self._get_client()

        # 1. Get current branch reference to get tree SHA
        ref_response = await client.get(
            f"/repos/{self.config.owner}/{self.config.repo}/git/ref/heads/{branch}"
        )
        ref_response.raise_for_status()
        current_commit_sha = ref_response.json()["object"]["sha"]

        # 2. Get the current commit to get its tree
        commit_response = await client.get(
            f"/repos/{self.config.owner}/{self.config.repo}/git/commits/{current_commit_sha}"
        )
        commit_response.raise_for_status()
        base_tree_sha = commit_response.json()["tree"]["sha"]

        # 3. Create blobs for each file

        tree_items = []
        for filepath, content in files.items():
            blob_payload = {
                "content": content,
                "encoding": "utf-8",
            }
            blob_response = await client.post(
                f"/repos/{self.config.owner}/{self.config.repo}/git/blobs", json=blob_payload
            )
            blob_response.raise_for_status()
            blob_sha = blob_response.json()["sha"]

            tree_items.append(
                {
                    "path": filepath,
                    "mode": "100644",  # Regular file
                    "type": "blob",
                    "sha": blob_sha,
                }
            )

        # 4. Create new tree with updated blobs
        tree_payload = {"base_tree": base_tree_sha, "tree": tree_items}

        tree_response = await client.post(
            f"/repos/{self.config.owner}/{self.config.repo}/git/trees", json=tree_payload
        )
        tree_response.raise_for_status()
        new_tree_sha = tree_response.json()["sha"]

        # 5. Create commit pointing to new tree
        commit_payload = {
            "message": message,
            "tree": new_tree_sha,
            "parents": [current_commit_sha],
        }
        if author:
            commit_payload["author"] = author

        new_commit_response = await client.post(
            f"/repos/{self.config.owner}/{self.config.repo}/git/commits", json=commit_payload
        )
        new_commit_response.raise_for_status()
        new_commit_sha: str = new_commit_response.json()["sha"]

        # 6. Update branch reference to point to new commit
        update_ref_payload = {"sha": new_commit_sha, "force": False}

        update_response = await client.patch(
            f"/repos/{self.config.owner}/{self.config.repo}/git/refs/heads/{branch}",
            json=update_ref_payload,
        )
        update_response.raise_for_status()

        logger.info("Committed %d files to %s at SHA %s", len(files), branch, new_commit_sha)
        return new_commit_sha

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

        body_sections.extend(f"- `{filepath}`" for filepath in data.changes)

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
