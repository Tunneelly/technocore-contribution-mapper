"""Read public sources and generate a local evidence report."""

import json
from pathlib import Path
from typing import Any

from contribution_mapper.github_reader import read_public_repository
from contribution_mapper.report import build_report
from contribution_mapper.technocore_reader import read_public_room


def run_mapper(
    owner: str,
    repository_name: str,
    room: str,
    *,
    artifact_url: str | None = None,
    commit: str | None = None,
    output: str = "contribution-report.json",
) -> dict[str, Any]:
    """Fetch public metadata and messages, then save a local JSON report."""
    repository = read_public_repository(owner, repository_name)
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

    output_path = Path(output)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report
