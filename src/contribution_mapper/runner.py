"""Read public sources and generate a local evidence report."""

import json
from pathlib import Path
from typing import Any

from contribution_mapper.github_reader import (
    check_commit_exists,
    read_public_repository,
)
from contribution_mapper.proof import verify_proof_file
from contribution_mapper.report import build_report
from contribution_mapper.technocore_reader import (
    read_public_room,
    read_public_room_export,
)

SOURCES = ("recent", "export")


def build_retrieval_coverage(
    room_data: dict[str, Any], source: str, evidence_count: int
) -> dict[str, Any]:
    """Describe exactly which messages were examined, and what that excludes."""
    messages = [m for m in room_data["messages"] if isinstance(m, dict)]
    seqs = [m["seq"] for m in messages if isinstance(m.get("seq"), int)]
    stamps = [m["ts"] for m in messages if isinstance(m.get("ts"), str)]
    truncated = bool(room_data.get("truncated", False))

    if source == "export":
        scope = (
            "The room's retained export, read in full."
            if not truncated
            else "The room's retained export, cut off at the size limit."
        )
    else:
        scope = "Only the most recent batch returned by the room endpoint."

    if evidence_count:
        outcome = "Matches were found in the examined messages (unverified)."
    else:
        outcome = (
            "No match in the examined messages. This does not show that no "
            "matching message was ever posted."
        )

    return {
        "method": source,
        "scope": scope,
        "messages_examined": len(messages),
        "first_seq_examined": min(seqs) if seqs else None,
        "last_seq_examined": max(seqs) if seqs else None,
        "earliest_ts_examined": min(stamps) if stamps else None,
        "latest_ts_examined": max(stamps) if stamps else None,
        "server_reported_first_seq": (
            room_data.get("first_seq") if source == "recent" else None
        ),
        "generation": room_data.get("generation"),
        "truncated": truncated,
        "malformed_records_skipped": room_data.get(
            "malformed_records_skipped", 0
        ),
        "retained_window_fully_examined": source == "export" and not truncated,
        "complete_history_searched": False,
        "note": (
            f"{outcome} The server keeps only a bounded window of recent "
            "messages, so older messages may no longer be retrievable."
        ),
    }


def run_mapper(
    owner: str,
    repository_name: str,
    room: str,
    *,
    artifact_url: str | None = None,
    commit: str | None = None,
    output: str = "contribution-report.json",
    source: str = "recent",
    proof_file: str | None = None,
) -> dict[str, Any]:
    """Fetch public metadata and messages, then save a local JSON report."""
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}.")

    # Verified first so a bad proof file fails before any network access.
    # Proof verification is reported separately from text-match evidence.
    if proof_file is not None:
        proof_result = verify_proof_file(
            proof_file,
            requested_artifact_url=artifact_url,
            requested_commit=commit,
        )
    else:
        proof_result = {"status": "not_supplied"}

    repository = read_public_repository(owner, repository_name)

    # Reported separately; a failed check never aborts the run.
    if commit is None:
        commit_result = {"status": "not_requested"}
    else:
        commit_result = check_commit_exists(owner, repository_name, commit)

    if source == "export":
        room_data = read_public_room_export(room)
    else:
        room_data = read_public_room(room)

    report = build_report(
        repository,
        [],
        technocore_messages=room_data["messages"],
        artifact_url=artifact_url or repository["html_url"],
        commit=commit,
    )

    report["technocore_source"] = {
        "room": room_data["room"],
        "count": room_data["count"],
        "last_seq": room_data["last_seq"],
        "source": room_data["source"],
    }

    report["report_version"] = "1.4"
    report["commit_check"] = commit_result
    report["proof_verification"] = proof_result
    report["retrieval_coverage"] = build_retrieval_coverage(
        room_data, source, report["evidence"]["record_count"]
    )

    output_path = Path(output)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report
