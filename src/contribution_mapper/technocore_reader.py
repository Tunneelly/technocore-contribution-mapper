"""Read and validate public Technocore room records."""

import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://technocore.chat"


class TechnocoreReaderError(Exception):
    """Raised when a public Technocore room cannot be read safely."""


def read_public_room(
    room: str,
    *,
    since: int | None = None,
    limit: int = 50,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 10.0,
) -> dict:
    """Fetch public room JSON and validate its stable response fields."""
    if not isinstance(room, str) or not room:
        raise ValueError("Room must be a non-empty string.")

    if room != room.strip() or len(room) > 48:
        raise ValueError("Room name is invalid.")

    if not (
        room[0].isascii()
        and room[0].isalnum()
        and all(
            char.isascii() and (char.isalnum() or char in "_-")
            for char in room
        )
    ):
        raise ValueError("Room name contains invalid characters.")

    if isinstance(since, bool) or (
        since is not None
        and (not isinstance(since, int) or since < 0)
    ):
        raise ValueError("since must be a non-negative integer.")

    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200.")

    if (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError("timeout must be a positive finite number.")

    if not isinstance(base_url, str):
        raise ValueError("Base URL must be a string.")

    base_url = base_url.rstrip("/")
    if not base_url.startswith("https://"):
        raise ValueError("Base URL must use HTTPS.")

    query = {"format": "json", "limit": limit}
    if since is not None:
        query["since"] = since

    url = f"{base_url}/r/{room}?{urlencode(query)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Technocore-Contribution-Mapper/0.1",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise TechnocoreReaderError(
            f"Technocore returned HTTP status {exc.code}."
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise TechnocoreReaderError(
            "Could not reach the Technocore service."
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TechnocoreReaderError(
            "Technocore returned invalid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise TechnocoreReaderError("Room response must be a JSON object.")

    if payload.get("room") != room:
        raise TechnocoreReaderError("Response room does not match the request.")

    count = payload.get("count")
    last_seq = payload.get("last_seq")
    messages = payload.get("messages")

    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise TechnocoreReaderError("Invalid room count.")

    if (
        isinstance(last_seq, bool)
        or not isinstance(last_seq, int)
        or last_seq < 0
    ):
        raise TechnocoreReaderError("Invalid last_seq cursor.")

    if not isinstance(messages, list) or any(
        not isinstance(message, dict) for message in messages
    ):
        raise TechnocoreReaderError("Invalid messages list.")

    return {
        "room": room,
        "count": count,
        "last_seq": last_seq,
        "messages": messages,
        "source": "Technocore public room API",
    }
