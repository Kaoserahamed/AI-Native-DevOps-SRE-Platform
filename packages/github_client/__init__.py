"""GitHub API client abstraction for incident and PR automation."""

__version__ = "0.1.0"

from packages.github_client.adapter import GitHubAdapter, GitHubConfig
from packages.github_client.client import (
    GitHubClient,
    GitHubIssue,
    GitHubPullRequest,
    GitHubRepository,
)

__all__ = [
    "GitHubAdapter",
    "GitHubClient",
    "GitHubConfig",
    "GitHubIssue",
    "GitHubPullRequest",
    "GitHubRepository",
]
