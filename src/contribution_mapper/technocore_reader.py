"""Read and validate public Technocore room records."""

import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://technocore.chat"


class TechnocoreReaderError(Exception):
    """Raised when a public Technocore room cannot be read safely."""


DEFAULT_EXPORT_MAX_BYTES = 16 * 1024 * 1024


def _validate_room_name(room: str) -> None:
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


def read_public_room_export(
    room: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 10.0,
    max_bytes: int = DEFAULT_EXPORT_MAX_BYTES,
) -> dict:
    """Read the room's retained JSONL export, bounded by ``max_bytes``.

    The export covers only what the server still retains, which may be
    far less than the room's full history. If the body exceeds
    ``max_bytes`` the read stops and ``truncated`` is True; a partial
    final line is discarded. Unparseable lines are counted, not hidden.
    """
    _validate_room_name(room)

    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer.")

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

    request = Request(
        f"{base_url}/r/{room}/export",
        headers={
            "Accept": "application/x-ndjson, text/plain",
            "User-Agent": "Technocore-Contribution-Mapper/0.1",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(max_bytes + 1)
    except HTTPError as exc:
        raise TechnocoreReaderError(
            f"Technocore returned HTTP status {exc.code}."
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise TechnocoreReaderError(
            "Could not reach the Technocore service."
        ) from exc

    truncated = len(body) > max_bytes
    if truncated:
        body = body[:max_bytes]
        # Drop the possibly partial final line.
        body = body[: body.rfind(b"\n") + 1]

    messages: list[dict] = []
    malformed = 0
    for raw_line in body.split(b"\n"):
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            malformed += 1
            continue
        if (
            not isinstance(record, dict)
            or isinstance(record.get("seq"), bool)
            or not isinstance(record.get("seq"), int)
        ):
            malformed += 1
            continue
        messages.append(record)

    seqs = [m["seq"] for m in messages]
    return {
        "room": room,
        "count": len(messages),
        "first_seq": min(seqs) if seqs else None,
        "last_seq": max(seqs) if seqs else None,
        "generation": None,
        "messages": messages,
        "truncated": truncated,
        "malformed_records_skipped": malformed,
        "source": "Technocore public room export",
    }


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

    first_seq = payload.get("first_seq")
    if first_seq is not None and (
        isinstance(first_seq, bool)
        or not isinstance(first_seq, int)
        or first_seq < 0
    ):
        raise TechnocoreReaderError("Invalid first_seq value.")

    generation = payload.get("generation")
    if generation is not None and (
        isinstance(generation, bool) or not isinstance(generation, int)
    ):
        raise TechnocoreReaderError("Invalid generation value.")

    return {
        "room": room,
        "count": count,
        "first_seq": first_seq,
        "last_seq": last_seq,
        "generation": generation,
        "messages": messages,
        "source": "Technocore public room API",
    }
