"""GitHub API client abstraction for incident and PR automation."""

__version__ = "0.1.0"

from packages.github_client.adapter import GitHubAdapter, GitHubConfig

__all__ = ["GitHubAdapter", "GitHubConfig"]
