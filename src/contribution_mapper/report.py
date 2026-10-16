"""Create structured reports from repository metadata and public evidence."""

from datetime import datetime, timezone
from typing import Any

from contribution_mapper.evidence import (
    EvidenceRecord,
    summarize_evidence,
)
from contribution_mapper.matcher import match_public_messages


def build_report(
    repository: dict[str, Any],
    evidence: list[EvidenceRecord],
    *,
    technocore_messages: list[dict[str, Any]] | None = None,
    artifact_url: str | None = None,
    commit: str | None = None,
) -> dict[str, Any]:
    """Build a report without treating metadata or text matches as proof."""
    if not isinstance(repository, dict):
        raise ValueError("Repository metadata must be a dictionary.")

    full_name = repository.get("full_name")
    html_url = repository.get("html_url")

    if not isinstance(full_name, str) or not full_name.strip():
        raise ValueError("Repository metadata must include full_name.")

    if not isinstance(html_url, str) or not html_url.startswith(
        ("https://", "http://")
    ):
        raise ValueError("Repository metadata must include a valid HTTP(S) URL.")

    if not isinstance(evidence, list):
        raise ValueError("Evidence must be provided as a list.")

    if not all(isinstance(item, EvidenceRecord) for item in evidence):
        raise ValueError("Every evidence item must be an EvidenceRecord.")

    combined_evidence = list(evidence)

    if technocore_messages is not None:
        if not isinstance(technocore_messages, list):
            raise ValueError("Technocore messages must be provided as a list.")

        combined_evidence.extend(
            match_public_messages(
                technocore_messages,
                artifact_url=artifact_url,
                commit=commit,
            )
        )

    return {
        "report_version": "1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": repository,
        "evidence": summarize_evidence(combined_evidence),
        "interpretation": {
            "repository_metadata_proves_authorship": False,
            "text_matches_prove_authorship": False,
            "text_matches_prove_did_control": False,
            "note": (
                "Repository metadata describes a public repository. "
                "Textual references in Technocore messages are leads for "
                "further investigation, not proof of authorship, commit "
                "ownership, signature validity, or control of a DID."
            ),
        },
    }
