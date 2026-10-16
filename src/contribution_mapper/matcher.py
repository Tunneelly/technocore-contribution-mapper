"""Conservative matching of public artifact references to room messages."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from .evidence import EvidenceRecord, EvidenceStatus, validate_public_url


_COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")


def _contains_exact_token(text: str, token: str) -> bool:
    """Match a full token, not a substring of a longer identifier."""
    start = 0
    while True:
        index = text.find(token, start)
        if index < 0:
            return False
        before_ok = index == 0 or not (
            text[index - 1].isalnum() or text[index - 1] in "_-"
        )
        end = index + len(token)
        after_ok = end == len(text) or not (
            text[end].isalnum() or text[end] in "_-"
        )
        if before_ok and after_ok:
            return True
        start = index + 1


def match_public_messages(
    messages: list[dict[str, Any]],
    *,
    artifact_url: str | None = None,
    commit: str | None = None,
) -> list[EvidenceRecord]:
    """Find messages that explicitly reference an artifact URL or full commit.

    A textual match is a lead for investigation, not proof of ownership,
    authorship, signature validity, or control of a DID.
    """
    if artifact_url is None and commit is None:
        raise ValueError("Provide an artifact_url, a commit, or both")

    normalized_url: str | None = None
    if artifact_url is not None:
        if not validate_public_url(artifact_url):
            raise ValueError("artifact_url must be a valid public HTTP(S) URL")
        normalized_url = artifact_url.rstrip("/")

    if commit is not None and not _COMMIT_PATTERN.fullmatch(commit):
        raise ValueError("commit must be a full 40-character Git SHA")

    matches: list[EvidenceRecord] = []

    for message in messages:
        if not isinstance(message, dict):
            continue

        text = message.get("text")
        if not isinstance(text, str):
            continue

        reasons: list[str] = []
        if normalized_url and normalized_url in text:
            reasons.append("exact artifact URL appears in message text")
        if commit and _contains_exact_token(text, commit):
            reasons.append("full commit SHA appears in message text")

        if not reasons:
            continue

        sender = message.get("from")
        if not isinstance(sender, str) or not sender.strip():
            sender = message.get("did")
        if not isinstance(sender, str) or not sender.strip():
            sender = "unknown"

        seq = message.get("seq")
        room = message.get("room")
        location = (
            f"room={room}, seq={seq}"
            if isinstance(room, str) and isinstance(seq, int)
            else f"seq={seq}"
            if isinstance(seq, int)
            else "message location unavailable"
        )

        matches.append(
            EvidenceRecord(
                source_url="https://technocore.chat",
                source_type="technocore_message_reference",
                claim=(
                    f"Message from {sender} references the requested artifact; "
                    f"{location}"
                ),
                status=EvidenceStatus.UNVERIFIED,
                details="; ".join(reasons)
                + ". Textual reference only; identity and authorship not proven.",
            )
        )

    return matches
