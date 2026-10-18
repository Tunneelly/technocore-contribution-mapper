import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from contribution_mapper.runner import build_retrieval_coverage, run_mapper
from contribution_mapper.technocore_reader import (
    TechnocoreReaderError,
    read_public_room,
    read_public_room_export,
)

SHA = "989c953696750b8ca60a0488052e68a5ad6273e6"
REPO = {
    "full_name": "example/project",
    "html_url": "https://github.com/example/project",
}


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]


def jsonl(*records):
    return ("\n".join(json.dumps(r) for r in records) + "\n").encode()


def msg(seq, text="hello", ts="2026-10-18T09:00:00Z"):
    return {"seq": seq, "ts": ts, "from": "did:key:zExample", "text": text}


class ExportReaderTests(unittest.TestCase):
    @patch("contribution_mapper.technocore_reader.urlopen")
    def test_reads_export_and_reports_range(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(jsonl(msg(5), msg(6), msg(7)))
        result = read_public_room_export("technocore")
        self.assertEqual(result["count"], 3)
        self.assertEqual((result["first_seq"], result["last_seq"]), (5, 7))
        self.assertFalse(result["truncated"])
        self.assertEqual(result["malformed_records_skipped"], 0)

    @patch("contribution_mapper.technocore_reader.urlopen")
    def test_counts_malformed_lines_instead_of_hiding_them(self, mock_urlopen):
        body = jsonl(msg(1)) + b"not json\n" + b'{"no_seq": true}\n' + jsonl(msg(2))
        mock_urlopen.return_value = FakeResponse(body)
        result = read_public_room_export("technocore")
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["malformed_records_skipped"], 2)

    @patch("contribution_mapper.technocore_reader.urlopen")
    def test_truncates_at_limit_and_drops_partial_line(self, mock_urlopen):
        body = jsonl(msg(1), msg(2), msg(3))
        limit = len(jsonl(msg(1))) + len(jsonl(msg(2))) + 10
        mock_urlopen.return_value = FakeResponse(body)
        result = read_public_room_export("technocore", max_bytes=limit)
        self.assertTrue(result["truncated"])
        self.assertEqual([m["seq"] for m in result["messages"]], [1, 2])
        self.assertEqual(result["malformed_records_skipped"], 0)

    @patch("contribution_mapper.technocore_reader.urlopen")
    def test_empty_export(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(b"")
        result = read_public_room_export("technocore")
        self.assertEqual(result["count"], 0)
        self.assertIsNone(result["first_seq"])

    def test_rejects_bad_inputs(self):
        with self.assertRaises(ValueError):
            read_public_room_export("Bad Room")
        with self.assertRaises(ValueError):
            read_public_room_export("technocore", max_bytes=0)
        with self.assertRaises(ValueError):
            read_public_room_export("technocore", base_url="http://x.example")

    @patch("contribution_mapper.technocore_reader.urlopen")
    def test_network_error_is_reported(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("down")
        with self.assertRaises(TechnocoreReaderError):
            read_public_room_export("technocore")


class RecentReaderFieldTests(unittest.TestCase):
    def payload(self, **extra):
        data = {"room": "lobby", "count": 1, "last_seq": 9, "messages": [msg(9)]}
        data.update(extra)
        return data

    @patch("contribution_mapper.technocore_reader.urlopen")
    def test_first_seq_and_generation_passed_through(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(
            json.dumps(self.payload(first_seq=9, generation=0)).encode()
        )
        result = read_public_room("lobby")
        self.assertEqual(result["first_seq"], 9)
        self.assertEqual(result["generation"], 0)

    @patch("contribution_mapper.technocore_reader.urlopen")
    def test_missing_optional_fields_are_none(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(
            json.dumps(self.payload()).encode()
        )
        result = read_public_room("lobby")
        self.assertIsNone(result["first_seq"])

    @patch("contribution_mapper.technocore_reader.urlopen")
    def test_rejects_malformed_first_seq(self, mock_urlopen):
        for bad in ("9", -1, True, 1.5):
            mock_urlopen.return_value = FakeResponse(
                json.dumps(self.payload(first_seq=bad)).encode()
            )
            with self.assertRaises(TechnocoreReaderError):
                read_public_room("lobby")


class CoverageTests(unittest.TestCase):
    def room_data(self, messages, **extra):
        data = {"room": "technocore", "count": len(messages),
                "first_seq": None, "last_seq": 0, "generation": None,
                "messages": messages}
        data.update(extra)
        return data

    def test_recent_never_claims_full_window_or_history(self):
        cov = build_retrieval_coverage(self.room_data([msg(10), msg(11)]), "recent", 0)
        self.assertFalse(cov["retained_window_fully_examined"])
        self.assertFalse(cov["complete_history_searched"])
        self.assertEqual((cov["first_seq_examined"], cov["last_seq_examined"]), (10, 11))
        self.assertIn("No match in the examined messages", cov["note"])

    def test_untruncated_export_examines_window_but_not_history(self):
        cov = build_retrieval_coverage(self.room_data([msg(10)]), "export", 0)
        self.assertTrue(cov["retained_window_fully_examined"])
        self.assertFalse(cov["complete_history_searched"])

    def test_truncated_export_is_not_a_full_window(self):
        cov = build_retrieval_coverage(
            self.room_data([msg(10)], truncated=True), "export", 0
        )
        self.assertFalse(cov["retained_window_fully_examined"])
        self.assertTrue(cov["truncated"])

    def test_empty_messages(self):
        cov = build_retrieval_coverage(self.room_data([]), "export", 0)
        self.assertEqual(cov["messages_examined"], 0)
        self.assertIsNone(cov["first_seq_examined"])

    def test_match_note_stays_unverified(self):
        cov = build_retrieval_coverage(self.room_data([msg(10)]), "export", 1)
        self.assertIn("unverified", cov["note"])


class RunnerCoverageTests(unittest.TestCase):
    @patch("contribution_mapper.runner.read_public_room_export")
    @patch("contribution_mapper.runner.read_public_repository")
    def test_export_source_older_announcement_not_in_window(self, mock_repo, mock_export):
        # Models the real case: target announcement (seq 100) is older than
        # the oldest retained message (seq 500), so it cannot be found.
        mock_repo.return_value = REPO
        mock_export.return_value = {
            "room": "technocore", "count": 2, "first_seq": 500, "last_seq": 501,
            "generation": None, "truncated": False, "malformed_records_skipped": 0,
            "messages": [msg(500), msg(501)], "source": "export",
        }
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.json"
            report = run_mapper("example", "project", "technocore",
                                commit=SHA, source="export", output=str(out))
            saved = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["evidence"]["record_count"], 0)
        cov = saved["retrieval_coverage"]
        self.assertEqual(cov["first_seq_examined"], 500)
        self.assertTrue(cov["retained_window_fully_examined"])
        self.assertFalse(cov["complete_history_searched"])
        self.assertEqual(saved["report_version"], "1.2")
        self.assertFalse(saved["interpretation"]["text_matches_prove_authorship"])

    @patch("contribution_mapper.runner.read_public_room_export")
    @patch("contribution_mapper.runner.read_public_repository")
    def test_match_in_export_is_unverified(self, mock_repo, mock_export):
        mock_repo.return_value = REPO
        mock_export.return_value = {
            "room": "technocore", "count": 1, "first_seq": 7, "last_seq": 7,
            "generation": None, "truncated": False, "malformed_records_skipped": 0,
            "messages": [msg(7, text=f"shipped {SHA}")], "source": "export",
        }
        with tempfile.TemporaryDirectory() as d:
            report = run_mapper("example", "project", "technocore", commit=SHA,
                                source="export", output=str(Path(d) / "r.json"))
        self.assertEqual(report["evidence"]["status_counts"]["unverified"], 1)

    @patch("contribution_mapper.runner.read_public_repository")
    def test_rejects_unknown_source(self, mock_repo):
        mock_repo.return_value = REPO
        with self.assertRaises(ValueError):
            run_mapper("example", "project", "lobby", source="history")

    @patch("contribution_mapper.runner.read_public_room")
    @patch("contribution_mapper.runner.read_public_repository")
    def test_default_source_still_recent_with_coverage(self, mock_repo, mock_room):
        mock_repo.return_value = REPO
        mock_room.return_value = {
            "room": "lobby", "count": 1, "first_seq": None, "last_seq": 3,
            "generation": None, "messages": [msg(3)], "source": "recent",
        }
        with tempfile.TemporaryDirectory() as d:
            report = run_mapper("example", "project", "lobby",
                                output=str(Path(d) / "r.json"))
        self.assertEqual(report["retrieval_coverage"]["method"], "recent")
        self.assertFalse(report["retrieval_coverage"]["retained_window_fully_examined"])


if __name__ == "__main__":
    unittest.main()
