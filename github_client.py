"""GitHub API client for fetching repository data."""

import base64
import os
from dataclasses import dataclass, field
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_API_BASE = "https://api.github.com"


@dataclass
class RepoFile:
    """A file or directory in a repository."""

    name: str
    path: str
    type: str  # "file" or "dir"
    size: int = 0
    children: list["RepoFile"] = field(default_factory=list)

    @property
    def is_dir(self) -> bool:
        return self.type == "dir"

    @property
    def extension(self) -> str:
        if "." in self.name:
            return self.name.rsplit(".", 1)[-1].lower()
        return ""


@dataclass
class RepoInfo:
    """Repository metadata."""

    full_name: str
    description: str
    language: str
    stars: int
    forks: int
    default_branch: str
    topics: list[str]
    size_kb: int
    open_issues: int
    license_name: str


class GitHubClient:
    """GitHub API client for reading repository contents."""

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN") or self._gh_cli_token()
        if not self.token:
            raise ValueError(
                "GITHUB_TOKEN not found. Set it in .env, as an env var, or install gh CLI."
            )
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
            }
        )

    @staticmethod
    def _gh_cli_token() -> Optional[str]:
        """Try to get token from gh CLI."""
        import subprocess

        try:
            result = subprocess.run(
                ["gh", "auth", "token"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def get_repo_info(self, owner: str, repo: str) -> RepoInfo:
        """Fetch repository metadata."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()
        d = resp.json()
        lic = d.get("license") or {}
        return RepoInfo(
            full_name=d.get("full_name", ""),
            description=d.get("description", "") or "",
            language=d.get("language", "") or "",
            stars=d.get("stargazers_count", 0),
            forks=d.get("forks_count", 0),
            default_branch=d.get("default_branch", "main"),
            topics=d.get("topics", []),
            size_kb=d.get("size", 0),
            open_issues=d.get("open_issues_count", 0),
            license_name=lic.get("spdx_id", "") or "",
        )

    def list_files(
        self,
        owner: str,
        repo: str,
        path: str = "",
        max_depth: int = 4,
        _current_depth: int = 0,
    ) -> list[RepoFile]:
        """Recursively list all files in a repository."""
        if _current_depth > max_depth:
            return []

        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        resp = self._session.get(url, timeout=15)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()

        data = resp.json()
        if isinstance(data, dict):
            data = [data]

        result: list[RepoFile] = []
        for entry in sorted(
            data, key=lambda e: (e.get("type") != "dir", e.get("name", "").lower())
        ):
            rf = RepoFile(
                name=entry.get("name", ""),
                path=entry.get("path", ""),
                type=entry.get("type", "file"),
                size=entry.get("size", 0),
            )
            if rf.is_dir:
                rf.children = self.list_files(
                    owner,
                    repo,
                    rf.path,
                    max_depth=max_depth,
                    _current_depth=_current_depth + 1,
                )
            result.append(rf)
        return result

    def read_file(self, owner: str, repo: str, file_path: str) -> str:
        """Read file content from a repository."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{file_path}"
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return data.get("content", "")

    def get_languages(self, owner: str, repo: str) -> dict[str, int]:
        """Get language breakdown (bytes per language)."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/languages"
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
