"""Read public GitHub repository metadata without authentication."""

import json
import re
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


_FULL_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")

COMMIT_CHECK_PROVES = (
    "GitHub resolves this exact commit hash under this repository's URL."
)
COMMIT_CHECK_DOES_NOT_PROVE = [
    "who wrote the commit or that the requester did",
    "that the commit is on any particular branch (GitHub can also resolve "
    "commits that exist only in forks of the repository)",
    "that the commit is still reachable from the default branch",
]


def check_commit_exists(
    owner: str,
    repository: str,
    commit: str,
    timeout: float = 10.0,
) -> dict:
    """Ask GitHub whether it serves ``commit`` under ``owner/repository``.

    Uses the SHA-only media type, so nothing about the commit's author or
    contents is fetched. Never raises for network or GitHub problems: the
    result's ``status`` is ``found``, ``not_found``, ``unavailable`` or
    ``skipped``. Invalid owner/repository/timeout still raise ValueError.
    """
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
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout <= 0
    ):
        raise ValueError("Timeout must be greater than zero.")

    owner = owner.strip()
    repository = repository.strip()
    result: dict = {
        "status": "skipped",
        "commit": None,
        "url": None,
        "proves": None,
        "does_not_prove": COMMIT_CHECK_DOES_NOT_PROVE,
        "reason": None,
        "source": "GitHub public API",
    }

    wanted = commit.strip().lower() if isinstance(commit, str) else ""
    if _FULL_SHA.fullmatch(wanted) is None:
        result["reason"] = (
            "Only a full 40- or 64-character commit hash can be checked."
        )
        return result

    result["commit"] = wanted
    request = Request(
        "https://api.github.com/repos/"
        f"{quote(owner, safe='')}/{quote(repository, safe='')}/commits/{wanted}",
        headers={
            "Accept": "application/vnd.github.sha",
            "User-Agent": "Technocore-Contribution-Mapper",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(256)
    except HTTPError as exc:
        if exc.code in (404, 422):
            result["status"] = "not_found"
            result["reason"] = (
                "GitHub does not serve this commit under this repository. "
                "It may not exist, may be mistyped, or may be private."
            )
        elif exc.code in (403, 429):
            result["status"] = "unavailable"
            result["reason"] = (
                "GitHub rate limit or access restriction encountered; "
                "the commit was not checked."
            )
        else:
            result["status"] = "unavailable"
            result["reason"] = f"GitHub returned HTTP status {exc.code}."
        return result
    except (URLError, TimeoutError, OSError):
        result["status"] = "unavailable"
        result["reason"] = "Could not reach the GitHub API."
        return result

    if not isinstance(body, bytes) or body.decode("ascii", "ignore").strip().lower() != wanted:
        result["status"] = "unavailable"
        result["reason"] = "GitHub returned an unexpected response."
        return result

    result["status"] = "found"
    result["url"] = (
        f"https://github.com/{quote(owner, safe='')}/"
        f"{quote(repository, safe='')}/commit/{wanted}"
    )
    result["proves"] = COMMIT_CHECK_PROVES
    return result
