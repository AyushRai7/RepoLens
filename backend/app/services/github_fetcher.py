import httpx
import re
import asyncio
from typing import Optional
from dataclasses import dataclass
from app.config import get_settings

settings = get_settings()

GITHUB_API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {settings.github_token}",
    "X-GitHub-Api-Version": "2022-11-28",
}

# File extensions we care about
CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".cpp",
    ".c",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".vue",
    ".svelte",
    ".html",
    ".css",
    ".scss",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".env.example",
    ".md",
    ".sql",
    ".prisma",
    ".graphql",
}

SKIP_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "__pycache__",
    ".next",
    "venv",
    ".venv",
    "env",
    "coverage",
    ".pytest_cache",
    "vendor",
    "target",
    "bin",
    "obj",
}


@dataclass
class RepoMeta:
    owner: str
    name: str
    full_name: str
    description: Optional[str]
    url: str
    default_branch: str
    stars: int
    forks: int
    language: Optional[str]
    topics: list
    license: Optional[str]
    last_commit_sha: Optional[str]


@dataclass
class FileInfo:
    path: str
    name: str
    extension: str
    size_bytes: int
    download_url: str


def get_github_client():
    return httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers=HEADERS,
    )


def parse_github_url(url: str) -> tuple[str, str]:
    """Extract owner and repo name from any GitHub URL format."""
    url = url.strip().rstrip("/")
    patterns = [
        r"github\.com[:/]([^/]+)/([^/.\s]+?)(?:\.git)?$",
        r"^([^/]+)/([^/]+)$",  # short form: owner/repo
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
    raise ValueError(f"Cannot parse GitHub URL: {url}")


async def fetch_repo_meta(owner: str, name: str) -> RepoMeta:
    """Fetch repository metadata from GitHub API."""
    async with get_github_client() as client:
        resp = await client.get(f"{GITHUB_API}/repos/{owner}/{name}", headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()

        # Get latest commit sha
        branch = data.get("default_branch", "main")
        commit_resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{name}/commits/{branch}", headers=HEADERS
        )
        last_sha = None
        if commit_resp.status_code == 200:
            last_sha = commit_resp.json().get("sha")

        return RepoMeta(
            owner=data["owner"]["login"],
            name=data["name"],
            full_name=data["full_name"],
            description=data.get("description"),
            url=data["html_url"],
            default_branch=branch,
            stars=data.get("stargazers_count", 0),
            forks=data.get("forks_count", 0),
            language=data.get("language"),
            topics=data.get("topics", []),
            license=(
                data.get("license", {}).get("name") if data.get("license") else None
            ),
            last_commit_sha=last_sha,
        )


async def fetch_file_tree(owner: str, name: str, branch: str) -> list[FileInfo]:
    """Fetch all files in repo using the Git tree API (single request, recursive)."""
    async with get_github_client() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{name}/git/trees/{branch}",
            params={"recursive": "1"},
            headers=HEADERS,
        )
        resp.raise_for_status()
        tree = resp.json().get("tree", [])

    files = []
    for item in tree:
        if item["type"] != "blob":
            continue

        path: str = item["path"]

        # Skip unwanted directories
        parts = path.split("/")
        if any(p in SKIP_DIRS for p in parts[:-1]):
            continue

        # Only code files
        ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
        if ext not in CODE_EXTENSIONS:
            continue

        # Skip very large files
        size = item.get("size", 0)
        if size > settings.max_file_size_kb * 1024:
            continue

        files.append(
            FileInfo(
                path=path,
                name=parts[-1],
                extension=ext,
                size_bytes=size,
                download_url=f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/{path}",
            )
        )

    return files[: settings.max_repo_files]


async def fetch_file_content(download_url: str) -> Optional[str]:
    """Download raw file content."""
    try:
        async with get_github_client() as client:
            resp = await client.get(download_url)
            if resp.status_code == 200:
                return resp.text
    except Exception:
        pass
    return None




async def fetch_commits(owner: str, name: str, limit: int = 50) -> list[dict]:
    """
    Fetch commits including stats and changed files.
    """

    async with get_github_client() as client:

        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{name}/commits",
            params={"per_page": limit},
            headers=HEADERS,
        )

        if resp.status_code != 200:
            return []

        commit_list = resp.json()

        async def fetch_commit_details(commit):
            sha = commit["sha"]

            detail_resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{name}/commits/{sha}",
                headers=HEADERS,
            )

            if detail_resp.status_code != 200:
                return None

            d = detail_resp.json()

            return {
                "sha": sha,
                "message": d["commit"]["message"],
                "author_name": d["commit"]["author"]["name"],
                "author_email": d["commit"]["author"]["email"],
                "committed_at": d["commit"]["author"]["date"],
                "additions": d.get("stats", {}).get("additions", 0),
                "deletions": d.get("stats", {}).get("deletions", 0),
                "files_changed": [f["filename"] for f in d.get("files", [])],
            }

        results = await asyncio.gather(*[fetch_commit_details(c) for c in commit_list])

        return [r for r in results if r]


async def fetch_languages(owner: str, name: str) -> dict:
    """Fetch language breakdown (bytes per language)."""
    async with get_github_client() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{name}/languages", headers=HEADERS
        )
        if resp.status_code != 200:
            return {}
        data = resp.json()
        total = sum(data.values()) or 1
        return {lang: round(bytes_ / total * 100, 1) for lang, bytes_ in data.items()}
