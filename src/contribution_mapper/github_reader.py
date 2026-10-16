"""Read public GitHub repository metadata without authentication."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class GitHubReaderError(Exception):
    """Raised when GitHub data cannot be retrieved or interpreted."""


def read_public_repository(
    owner: str,
    repository: str,
    timeout: float = 10.0,
) -> dict:
    """Return selected metadata for a public GitHub repository."""
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("Owner must not be empty.")

    if not isinstance(repository, str) or not repository.strip():
        raise ValueError("Repository name must not be empty.")

    if (
        "/" in owner
        or "/" in repository
        or owner in {".", ".."}
        or repository in {".", ".."}
        or any(ord(char) < 32 for char in owner + repository)
    ):
        raise ValueError("Provide a valid owner and repository name.")

    if timeout <= 0:
        raise ValueError("Timeout must be greater than zero.")

    owner = owner.strip()
    repository = repository.strip()
    url = (
        "https://api.github.com/repos/"
        f"{quote(owner, safe='')}/{quote(repository, safe='')}"
    )

    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Technocore-Contribution-Mapper",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as exc:
        if exc.code == 404:
            raise GitHubReaderError(
                "Repository not found or not publicly accessible."
            ) from exc
        if exc.code == 403 or exc.code == 429:
            raise GitHubReaderError(
                "GitHub rate limit or access restriction encountered."
            ) from exc
        raise GitHubReaderError(
            f"GitHub returned HTTP status {exc.code}."
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise GitHubReaderError(
            "Could not reach the GitHub API."
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise GitHubReaderError(
            "GitHub returned invalid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise GitHubReaderError("Unexpected GitHub response format.")

    required = ("full_name", "html_url")
    if any(not isinstance(payload.get(key), str) for key in required):
        raise GitHubReaderError(
            "GitHub response is missing required repository fields."
        )

    license_info = payload.get("license")
    if isinstance(license_info, dict):
        license_name = license_info.get("spdx_id")
    else:
        license_name = None

    return {
        "full_name": payload["full_name"],
        "html_url": payload["html_url"],
        "description": payload.get("description"),
        "default_branch": payload.get("default_branch"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "pushed_at": payload.get("pushed_at"),
        "stars": payload.get("stargazers_count"),
        "forks": payload.get("forks_count"),
        "open_issues": payload.get("open_issues_count"),
        "license_spdx_id": license_name,
        "source": "GitHub public API",
    }
