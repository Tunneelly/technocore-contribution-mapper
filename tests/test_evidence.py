import unittest

from contribution_mapper.evidence import (
    EvidenceRecord,
    EvidenceStatus,
    summarize_evidence,
    validate_public_url,
)


class EvidenceTests(unittest.TestCase):
    def test_record_defaults_to_unverified(self):
        record = EvidenceRecord(
            source_url="https://github.com/example/project",
            source_type="github_repository",
            claim="The repository exists.",
        )
        self.assertEqual(record.status, EvidenceStatus.UNVERIFIED)
        self.assertTrue(record.observed_at)

    def test_record_serializes_status(self):
        record = EvidenceRecord(
            source_url="https://example.com/evidence",
            source_type="web_page",
            claim="A sample claim.",
            status=EvidenceStatus.VERIFIED,
        )
        self.assertEqual(record.to_dict()["status"], "verified")

    def test_invalid_url_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_public_url("file:///etc/passwd")

    def test_url_with_embedded_credentials_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_public_url("https://user:password@example.com/")

    def test_empty_claim_is_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceRecord(
                source_url="https://example.com",
                source_type="web_page",
                claim="   ",
            )

    def test_summary_preserves_status_counts(self):
        records = [
            EvidenceRecord(
                source_url="https://example.com/a",
                source_type="web_page",
                claim="Claim A",
                status=EvidenceStatus.VERIFIED,
            ),
            EvidenceRecord(
                source_url="https://example.com/b",
                source_type="web_page",
                claim="Claim B",
            ),
        ]

        summary = summarize_evidence(records)
        self.assertEqual(summary["record_count"], 2)
        self.assertEqual(summary["status_counts"]["verified"], 1)
        self.assertEqual(summary["status_counts"]["unverified"], 1)


if __name__ == "__main__":
    unittest.main()
