import unittest

from contribution_mapper.evidence import EvidenceStatus
from contribution_mapper.matcher import match_public_messages


URL = "https://github.com/example/project"
COMMIT = "a" * 40


class MatcherTests(unittest.TestCase):
    def test_matches_exact_artifact_url(self):
        results = match_public_messages(
            [{"from": "did:example:123", "seq": 7,
              "text": f"My work: {URL}"}],
            artifact_url=URL,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, EvidenceStatus.UNVERIFIED)
        self.assertIn("did:example:123", results[0].claim)

    def test_matches_full_commit(self):
        results = match_public_messages(
            [{"from": "did:example:123", "seq": 8,
              "text": f"Commit {COMMIT}"}],
            commit=COMMIT,
        )
        self.assertEqual(len(results), 1)
        self.assertIn("full commit SHA", results[0].details)

    def test_does_not_match_partial_commit(self):
        results = match_public_messages(
            [{"text": f"Commit {COMMIT[:12]}"}],
            commit=COMMIT,
        )
        self.assertEqual(results, [])

    def test_does_not_match_commit_inside_longer_token(self):
        results = match_public_messages(
            [{"text": f"x{COMMIT}"}],
            commit=COMMIT,
        )
        self.assertEqual(results, [])

    def test_ignores_non_message_records(self):
        results = match_public_messages(
            [{"text": None}, "not a message", {"text": "unrelated"}],
            artifact_url=URL,
        )
        self.assertEqual(results, [])

    def test_message_without_sender_is_not_discarded(self):
        results = match_public_messages(
            [{"seq": 9, "text": f"Reference: {URL}"}],
            artifact_url=URL,
        )
        self.assertEqual(len(results), 1)
        self.assertIn("unknown", results[0].claim)

    def test_requires_an_artifact_or_commit(self):
        with self.assertRaises(ValueError):
            match_public_messages([])

    def test_rejects_short_commit(self):
        with self.assertRaises(ValueError):
            match_public_messages([], commit="abc")

    def test_rejects_invalid_artifact_url(self):
        with self.assertRaises(ValueError):
            match_public_messages([], artifact_url="javascript:alert(1)")


if __name__ == "__main__":
    unittest.main()
