import unittest

from contribution_mapper.evidence import EvidenceRecord, EvidenceStatus
from contribution_mapper.report import build_report


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.repository = {
            "full_name": "example/project",
            "html_url": "https://github.com/example/project",
            "description": "Example repository",
        }

    def test_builds_report_with_evidence_summary(self):
        evidence = [
            EvidenceRecord(
                source_url="https://github.com/example/project",
                source_type="github_repository",
                claim="The public repository exists.",
            )
        ]

        report = build_report(self.repository, evidence)

        self.assertEqual(report["report_version"], "1.1")
        self.assertEqual(report["repository"]["full_name"], "example/project")
        self.assertEqual(report["evidence"]["record_count"], 1)
        self.assertFalse(
            report["interpretation"]["repository_metadata_proves_authorship"]
        )

    def test_preserves_evidence_status(self):
        evidence = [
            EvidenceRecord(
                source_url="https://example.com/evidence",
                source_type="web_page",
                claim="Sample claim",
                status=EvidenceStatus.UNVERIFIED,
            )
        ]

        report = build_report(self.repository, evidence)
        self.assertEqual(
            report["evidence"]["status_counts"]["unverified"], 1
        )

    def test_rejects_missing_repository_name(self):
        with self.assertRaises(ValueError):
            build_report({"html_url": "https://github.com/example/project"}, [])

    def test_rejects_invalid_repository_url(self):
        with self.assertRaises(ValueError):
            build_report(
                {"full_name": "example/project", "html_url": "file:///tmp/x"},
                [],
            )

    def test_rejects_non_evidence_items(self):
        with self.assertRaises(ValueError):
            build_report(self.repository, ["not an evidence record"])


if __name__ == "__main__":
    unittest.main()


class ReportMatcherIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.repository = {
            "full_name": "example/project",
            "html_url": "https://github.com/example/project",
        }

    def test_includes_technocore_text_match_as_unverified(self):
        from contribution_mapper.evidence import EvidenceStatus

        report = build_report(
            self.repository,
            [],
            technocore_messages=[
                {
                    "from": "did:example:123",
                    "seq": 42,
                    "text": "Project: https://github.com/example/project",
                }
            ],
            artifact_url="https://github.com/example/project",
        )

        self.assertEqual(report["report_version"], "1.1")
        self.assertEqual(report["evidence"]["record_count"], 1)
        self.assertEqual(
            report["evidence"]["status_counts"]["unverified"], 1
        )
        self.assertFalse(
            report["interpretation"]["text_matches_prove_authorship"]
        )
        self.assertFalse(
            report["interpretation"]["text_matches_prove_did_control"]
        )

    def test_report_without_technocore_messages_still_works(self):
        report = build_report(self.repository, [])
        self.assertEqual(report["evidence"]["record_count"], 0)

    def test_combines_existing_and_matched_evidence(self):
        from contribution_mapper.evidence import EvidenceRecord

        existing = EvidenceRecord(
            source_url="https://example.org/evidence",
            source_type="manual_note",
            claim="A separate observation",
        )

        report = build_report(
            self.repository,
            [existing],
            technocore_messages=[
                {
                    "from": "did:example:123",
                    "seq": 43,
                    "text": "Commit reference for "
                    + "a" * 40,
                }
            ],
            commit="a" * 40,
        )

        self.assertEqual(report["evidence"]["record_count"], 2)
