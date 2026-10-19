import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from contribution_mapper import proof as proof_module
from contribution_mapper.proof import (
    MAX_PROOF_BYTES,
    contribution_payload,
    verify_proof_data,
    verify_proof_file,
)
from contribution_mapper.runner import run_mapper

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    HAVE_CRYPTO = True
except ImportError:  # pragma: no cover
    HAVE_CRYPTO = False

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
URL = "https://github.com/example/project"
SHA = "989c953696750b8ca60a0488052e68a5ad6273e6"
REPO = {"full_name": "example/project", "html_url": URL}


def b58encode(data: bytes) -> str:
    zeroes = len(data) - len(data.lstrip(b"\x00"))
    number = int.from_bytes(data, "big")
    out = ""
    while number:
        number, rem = divmod(number, 58)
        out = ALPHABET[rem] + out
    return "1" * zeroes + out


def did_for(key) -> str:
    raw = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return "did:key:z" + b58encode(b"\xed\x01" + raw)


def make_proof(key, url=URL, commit=SHA, did=None):
    sig = base64.urlsafe_b64encode(
        key.sign(contribution_payload(url, commit))
    ).decode().rstrip("=")
    return {
        "schema": "technocore-contribution-proof-v1",
        "did": did or did_for(key),
        "artifact_url": url,
        "commit": commit.lower(),
        "signature": sig,
    }


@unittest.skipUnless(HAVE_CRYPTO, "cryptography not installed")
class ValidAndInvalidProofTests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()

    def test_valid_proof(self):
        result = verify_proof_data(make_proof(self.key))
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["commit"], SHA)
        self.assertIn("exact artifact URL and commit", result["proves"])
        self.assertTrue(result["does_not_prove"])

    def test_valid_proof_with_64_char_commit_and_uppercase(self):
        commit = ("AB" * 32)
        result = verify_proof_data(make_proof(self.key, commit=commit))
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["commit"], commit.lower())

    def test_tampered_commit_is_invalid(self):
        proof = make_proof(self.key)
        proof["commit"] = "0" * 40
        self.assertEqual(verify_proof_data(proof)["status"], "invalid")

    def test_tampered_url_is_invalid(self):
        proof = make_proof(self.key)
        proof["artifact_url"] = "https://github.com/evil/project"
        self.assertEqual(verify_proof_data(proof)["status"], "invalid")

    def test_claiming_someone_elses_did_is_invalid(self):
        other = Ed25519PrivateKey.generate()
        proof = make_proof(self.key, did=did_for(other))
        result = verify_proof_data(proof)
        self.assertEqual(result["status"], "invalid")
        self.assertIsNone(result["proves"])

    def test_request_matching_flags(self):
        proof = make_proof(self.key)
        ok = verify_proof_data(
            proof, requested_artifact_url=URL + "/", requested_commit=SHA.upper()
        )
        self.assertTrue(ok["artifact_url_matches_request"])
        self.assertTrue(ok["commit_matches_request"])
        bad = verify_proof_data(
            proof, requested_artifact_url="https://github.com/other/x",
            requested_commit="1" * 40,
        )
        self.assertEqual(bad["status"], "valid")  # valid, but about something else
        self.assertFalse(bad["artifact_url_matches_request"])
        self.assertFalse(bad["commit_matches_request"])

    def test_unrequested_matches_are_none(self):
        result = verify_proof_data(make_proof(self.key))
        self.assertIsNone(result["artifact_url_matches_request"])
        self.assertIsNone(result["commit_matches_request"])


class UnavailableTests(unittest.TestCase):
    @unittest.skipUnless(HAVE_CRYPTO, "cryptography not installed")
    def test_without_crypto_library_never_reports_valid(self):
        proof = make_proof(Ed25519PrivateKey.generate())
        with patch.object(proof_module, "_load_crypto", return_value=None):
            result = verify_proof_data(proof)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["proves"])
        self.assertIn("pip install cryptography", result["reason"])


class MalformedProofTests(unittest.TestCase):
    def good_shape(self):
        key_did = "did:key:z6Mk" + "1" * 44
        return {
            "schema": "technocore-contribution-proof-v1",
            "did": key_did,
            "artifact_url": URL,
            "commit": SHA,
            "signature": "A" * 86,
        }

    def assert_malformed(self, proof):
        result = verify_proof_data(proof)
        self.assertEqual(result["status"], "malformed", result)
        self.assertIsNone(result["proves"])
        self.assertTrue(result["reason"])

    def test_not_an_object(self):
        for bad in (None, [], "x", 5):
            self.assert_malformed(bad)

    def test_wrong_schema_and_missing_fields(self):
        p = self.good_shape(); p["schema"] = "other"; self.assert_malformed(p)
        for field in ("did", "artifact_url", "commit", "signature"):
            p = self.good_shape(); del p[field]; self.assert_malformed(p)
            p = self.good_shape(); p[field] = 5; self.assert_malformed(p)

    def test_bad_did(self):
        for did in ("z6Mk" + "1" * 44, "did:key:z6Mk123", "did:web:example.com",
                    "did:key:z6Mk" + "0" * 44):
            p = self.good_shape(); p["did"] = did; self.assert_malformed(p)

    def test_bad_signature_shape(self):
        for sig in ("short", "A" * 87, "A" * 85 + "!"):
            p = self.good_shape(); p["signature"] = sig; self.assert_malformed(p)

    def test_non_canonical_signature_encoding(self):
        p = self.good_shape(); p["signature"] = "A" * 85 + "B"
        self.assert_malformed(p)

    def test_bad_urls(self):
        for url in ("http://github.com/x/y", "https://user:pw@github.com/x/y",
                    "https://github.com/x/y#frag", " https://github.com/x/y",
                    "github.com/x/y", "https://"):
            p = self.good_shape(); p["artifact_url"] = url; self.assert_malformed(p)

    def test_bad_commits(self):
        for commit in ("abc123", "g" * 40, SHA[:-1], SHA + "0"):
            p = self.good_shape(); p["commit"] = commit; self.assert_malformed(p)


class ProofFileTests(unittest.TestCase):
    def test_missing_file(self):
        with self.assertRaises(ValueError):
            verify_proof_file("/nonexistent/proof.json")

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "p.json"
            path.write_text("not json")
            with self.assertRaises(ValueError):
                verify_proof_file(str(path))

    def test_too_large(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "p.json"
            path.write_bytes(b" " * (MAX_PROOF_BYTES + 1))
            with self.assertRaises(ValueError):
                verify_proof_file(str(path))

    @unittest.skipUnless(HAVE_CRYPTO, "cryptography not installed")
    def test_valid_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "p.json"
            path.write_text(json.dumps(make_proof(Ed25519PrivateKey.generate())))
            self.assertEqual(verify_proof_file(str(path))["status"], "valid")


class RunnerProofTests(unittest.TestCase):
    def room(self):
        return {"room": "lobby", "count": 0, "first_seq": None, "last_seq": 1,
                "generation": None, "messages": [], "source": "recent"}

    @patch("contribution_mapper.runner.read_public_room")
    @patch("contribution_mapper.runner.read_public_repository")
    def test_no_proof_supplied(self, mock_repo, mock_room):
        mock_repo.return_value = REPO
        mock_room.return_value = self.room()
        with tempfile.TemporaryDirectory() as d:
            report = run_mapper("example", "project", "lobby",
                                output=str(Path(d) / "r.json"))
        self.assertEqual(report["proof_verification"], {"status": "not_supplied"})

    @patch("contribution_mapper.runner.read_public_room")
    @patch("contribution_mapper.runner.read_public_repository")
    def test_bad_proof_file_fails_before_network(self, mock_repo, mock_room):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                run_mapper("example", "project", "lobby",
                           proof_file=str(Path(d) / "missing.json"),
                           output=str(Path(d) / "r.json"))
            self.assertFalse((Path(d) / "r.json").exists())
        mock_repo.assert_not_called()
        mock_room.assert_not_called()

    @unittest.skipUnless(HAVE_CRYPTO, "cryptography not installed")
    @patch("contribution_mapper.runner.check_commit_exists")
    @patch("contribution_mapper.runner.read_public_room")
    @patch("contribution_mapper.runner.read_public_repository")
    def test_valid_proof_stays_separate_from_evidence(
        self, mock_repo, mock_room, mock_commit
    ):
        mock_commit.return_value = {"status": "found"}
        mock_repo.return_value = REPO
        mock_room.return_value = self.room()
        with tempfile.TemporaryDirectory() as d:
            proof_path = Path(d) / "p.json"
            proof_path.write_text(json.dumps(make_proof(Ed25519PrivateKey.generate())))
            report = run_mapper("example", "project", "lobby",
                                artifact_url=URL, commit=SHA,
                                proof_file=str(proof_path),
                                output=str(Path(d) / "r.json"))
        self.assertEqual(report["proof_verification"]["status"], "valid")
        self.assertTrue(report["proof_verification"]["commit_matches_request"])
        self.assertEqual(report["evidence"]["record_count"], 0)
        self.assertFalse(report["interpretation"]["text_matches_prove_authorship"])
        self.assertFalse(report["interpretation"]["text_matches_prove_did_control"])


if __name__ == "__main__":
    unittest.main()
