"""Structured evidence records for the Technocore Contribution Mapper."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib.parse import urlparse


class EvidenceStatus(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    CONFLICTING = "conflicting"
    UNKNOWN = "unknown"


def validate_public_url(value: str) -> str:
    """Accept ordinary HTTP(S) URLs without claiming their contents are verified."""
    if not isinstance(value, str):
        raise ValueError("URL must be a string.")

    parsed = urlparse(value.strip())

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Provide a valid HTTP(S) URL without embedded credentials.")

    return value.strip()


@dataclass(frozen=True)
class EvidenceRecord:
    """A source record with an explicit verification status."""

    source_url: str
    source_type: str
    claim: str
    status: EvidenceStatus = EvidenceStatus.UNVERIFIED
    observed_at: str = ""
    details: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_url", validate_public_url(self.source_url)
        )

        if not self.source_type.strip():
            raise ValueError("source_type cannot be empty.")

        if not self.claim.strip():
            raise ValueError("claim cannot be empty.")

        if not isinstance(self.status, EvidenceStatus):
            raise ValueError("status must be an EvidenceStatus value.")

        if not self.observed_at:
            timestamp = datetime.now(timezone.utc).isoformat()
            object.__setattr__(self, "observed_at", timestamp)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        result = asdict(self)
        result["status"] = self.status.value
        return result


def summarize_evidence(
    records: list[EvidenceRecord],
) -> dict[str, Any]:
    """Summarize records without upgrading their verification status."""
    counts = {status.value: 0 for status in EvidenceStatus}

    for record in records:
        counts[record.status.value] += 1

    return {
        "record_count": len(records),
        "status_counts": counts,
        "records": [record.to_dict() for record in records],
    }
