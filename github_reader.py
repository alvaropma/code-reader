# github_reader.py

import base64
import os
from typing import List, Optional

import requests
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


class GitHubClient:
    """
    Simple GitHub API client to list files and read file contents
    from public repositories.
    """

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or GITHUB_TOKEN
        if not self.token:
            raise ValueError(
                "GITHUB_TOKEN not found. Set it in your .env file as GITHUB_TOKEN=..."
            )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }

    def list_repository_files(
        self,
        owner: str,
        repo: str,
        path: str = "",
    ) -> List[dict]:
        """
        List files in a GitHub repository at a given path.

        Returns a list of dicts with keys:
        - name
        - path
        - type ("file" or "dir")
        - download_url (may be None for dirs)
        """
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        response = requests.get(url, headers=self._headers(), timeout=15)

        if response.status_code == 404:
            raise ValueError(f"Repository or path not found: {owner}/{repo}/{path}")
        if not response.ok:
            raise RuntimeError(
                f"GitHub API error {response.status_code}: {response.text}"
            )

        data = response.json()

        # If it's a single file, GitHub returns a dict, not a list
        if isinstance(data, dict):
            return [data]

        return data

    def read_file_content(
        self,
        owner: str,
        repo: str,
        file_path: str,
    ) -> str:
        """
        Read the content of a file in a GitHub repository.

        Returns the file content as a UTF-8 string.
        """
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{file_path}"
        response = requests.get(url, headers=self._headers(), timeout=15)

        if response.status_code == 404:
            raise ValueError(
                f"File not found: {owner}/{repo}/{file_path}"
            )
        if not response.ok:
            raise RuntimeError(
                f"GitHub API error {response.status_code}: {response.text}"
            )

        data = response.json()

        if data.get("encoding") == "base64":
            content_bytes = base64.b64decode(data["content"])
            return content_bytes.decode("utf-8", errors="replace")

        # Fallback if GitHub ever returns raw content
        return data.get("content", "")

    def list_python_files(
        self,
        owner: str,
        repo: str,
        path: str = "",
        max_depth: int = 3,
        _current_depth: int = 0,
    ) -> List[str]:
        """
        Recursively list Python files (ending in .py) in a repository.

        max_depth limits recursion to avoid extremely deep trees.
        """
        if _current_depth > max_depth:
            return []

        entries = self.list_repository_files(owner, repo, path)
        python_files: List[str] = []

        for entry in entries:
            entry_type = entry.get("type")
            entry_path = entry.get("path")

            if entry_type == "file" and entry_path.endswith(".py"):
                python_files.append(entry_path)
            elif entry_type == "dir":
                python_files.extend(
                    self.list_python_files(
                        owner,
                        repo,
                        entry_path,
                        max_depth=max_depth,
                        _current_depth=_current_depth + 1,
                    )
                )

        return python_files
