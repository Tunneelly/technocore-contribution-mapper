"""Verify a signed Technocore contribution proof, separately from text matching.

A valid proof shows that someone holding the private key for the proof's
DID signed this exact artifact URL and commit. It does not show who that
person is, that they wrote the commit, or that the commit is in any
particular repository. Verification needs the optional ``cryptography``
package; without it the result is "unavailable", never "valid".
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCHEMA = "technocore-contribution-proof-v1"
PAYLOAD_SCHEMA = "technocore-contribution-v1"
MAX_PROOF_BYTES = 64 * 1024

_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_INDEX = {char: i for i, char in enumerate(_ALPHABET)}
_MULTICODEC_ED25519 = b"\xed\x01"
_MULTIBASE_LENGTH = 48
_SIGNATURE_PATTERN = re.compile(r"[A-Za-z0-9_-]{86}")
_COMMIT_PATTERN = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})")

PROVES = (
    "Whoever produced this proof held the private key for the stated DID "
    "when they signed this exact artifact URL and commit."
)
DOES_NOT_PROVE = [
    "who controls the DID in real life",
    "that the signer wrote the commit or any code in it",
    "that the commit exists in, or was pushed to, the artifact repository",
    "that any Technocore message was sent by the same key",
    "that the DID holds funds or can receive tokens",
]


class ProofFormatError(ValueError):
    """The proof is not shaped like a supported contribution proof."""


def _load_crypto():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
    except ImportError:
        return None
    return Ed25519PublicKey, InvalidSignature


def _base58_decode(value: str) -> bytes:
    number = 0
    for char in value:
        if char not in _INDEX:
            raise ProofFormatError("DID contains an invalid base58 character.")
        number = number * 58 + _INDEX[char]
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    zeroes = len(value) - len(value.lstrip("1"))
    return b"\x00" * zeroes + decoded


def _public_key_bytes(did: str) -> bytes:
    prefix = "did:key:"
    if not did.startswith(prefix):
        raise ProofFormatError("DID must start with 'did:key:'.")
    multibase = did[len(prefix):]
    if len(multibase) != _MULTIBASE_LENGTH or not multibase.startswith("z6Mk"):
        raise ProofFormatError("DID is not a canonical Ed25519 did:key.")
    decoded = _base58_decode(multibase[1:])
    if len(decoded) != 34 or not decoded.startswith(_MULTICODEC_ED25519):
        raise ProofFormatError("DID does not contain an ed25519 public key.")
    return decoded[2:]


def contribution_payload(artifact_url: str, commit: str) -> bytes:
    """Rebuild the exact bytes the proof's signature must cover."""
    if artifact_url != artifact_url.strip():
        raise ProofFormatError("artifact_url has surrounding whitespace.")
    try:
        parsed = urlsplit(artifact_url)
        parsed.port  # raises ValueError for an invalid port
    except ValueError as exc:
        raise ProofFormatError("artifact_url is malformed.") from exc
    if parsed.scheme != "https" or not parsed.netloc or parsed.fragment:
        raise ProofFormatError(
            "artifact_url must be an absolute HTTPS URL without a fragment."
        )
    if parsed.username is not None or parsed.password is not None:
        raise ProofFormatError("artifact_url must not embed credentials.")
    if _COMMIT_PATTERN.fullmatch(commit) is None:
        raise ProofFormatError("commit must be a full 40- or 64-character hex revision.")
    record = {
        "artifact_url": artifact_url,
        "commit": commit.lower(),
        "schema": PAYLOAD_SCHEMA,
    }
    return json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _decode_signature(signature: str) -> bytes:
    if _SIGNATURE_PATTERN.fullmatch(signature) is None:
        raise ProofFormatError("signature must be 86 unpadded base64url characters.")
    raw = base64.urlsafe_b64decode(signature + "==")
    if base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != signature:
        raise ProofFormatError("signature encoding is not canonical.")
    return raw


def verify_proof_data(
    proof: Any,
    *,
    requested_artifact_url: str | None = None,
    requested_commit: str | None = None,
) -> dict[str, Any]:
    """Return a structured, non-raising verification result.

    ``status`` is one of: valid, invalid, malformed, unavailable.
    """
    result: dict[str, Any] = {
        "status": "malformed",
        "did": None,
        "artifact_url": None,
        "commit": None,
        "artifact_url_matches_request": None,
        "commit_matches_request": None,
        "proves": None,
        "does_not_prove": DOES_NOT_PROVE,
        "reason": None,
    }

    try:
        if not isinstance(proof, dict):
            raise ProofFormatError("Proof must be a JSON object.")
        if proof.get("schema") != SCHEMA:
            raise ProofFormatError("Unsupported proof schema.")
        fields = ("did", "artifact_url", "commit", "signature")
        if any(not isinstance(proof.get(f), str) for f in fields):
            raise ProofFormatError("Proof is missing required string fields.")

        did, url, commit, signature = (proof[f] for f in fields)
        key_bytes = _public_key_bytes(did)
        payload = contribution_payload(url, commit)
        raw_signature = _decode_signature(signature)
    except ProofFormatError as exc:
        result["reason"] = str(exc)
        return result

    result["did"] = did
    result["artifact_url"] = url
    result["commit"] = commit.lower()
    if requested_artifact_url is not None:
        result["artifact_url_matches_request"] = (
            url.rstrip("/") == requested_artifact_url.rstrip("/")
        )
    if requested_commit is not None:
        result["commit_matches_request"] = commit.lower() == requested_commit.lower()

    crypto = _load_crypto()
    if crypto is None:
        result["status"] = "unavailable"
        result["reason"] = (
            "The 'cryptography' package is not installed, so the signature "
            "was not checked. Run: pip install cryptography"
        )
        return result

    public_key_class, invalid_signature = crypto
    try:
        public_key_class.from_public_bytes(key_bytes).verify(raw_signature, payload)
    except invalid_signature:
        result["status"] = "invalid"
        result["reason"] = "Signature does not match the DID and payload."
        return result
    except ValueError:
        result["status"] = "malformed"
        result["reason"] = "DID contains an invalid Ed25519 public key."
        return result

    result["status"] = "valid"
    result["proves"] = PROVES
    return result


def verify_proof_file(path: str, **requested: str | None) -> dict[str, Any]:
    """Read a proof JSON file (size-capped) and verify it."""
    file_path = Path(path).expanduser()
    try:
        with file_path.open("rb") as handle:
            body = handle.read(MAX_PROOF_BYTES + 1)
    except OSError as exc:
        raise ValueError(f"Cannot read proof file: {exc.strerror or exc}") from exc
    if len(body) > MAX_PROOF_BYTES:
        raise ValueError("Proof file is too large.")
    try:
        proof = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Proof file is not valid JSON.") from exc
    return verify_proof_data(proof, **requested)
