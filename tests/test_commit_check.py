import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from contribution_mapper.github_reader import check_commit_exists
from contribution_mapper.runner import run_mapper

SHA = "989c953696750b8ca60a0488052e68a5ad6273e6"
REPO = {"full_name": "example/project", "html_url": "https://github.com/example/project"}


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]


def http_error(code):
    return HTTPError("https://api.github.com/x", code, "err", {}, None)


class CheckCommitExistsTests(unittest.TestCase):
    @patch("contribution_mapper.github_reader.urlopen")
    def test_found(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(SHA.encode())
        result = check_commit_exists("example", "project", SHA)
        self.assertEqual(result["status"], "found")
        self.assertEqual(result["url"], f"https://github.com/example/project/commit/{SHA}")
        self.assertIn("exact commit hash", result["proves"])
        self.assertTrue(result["does_not_prove"])
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.get_header("Accept"), "application/vnd.github.sha")
        self.assertTrue(request.full_url.endswith(f"/repos/example/project/commits/{SHA}"))

    @patch("contribution_mapper.github_reader.urlopen")
    def test_uppercase_input_and_trailing_newline(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse((SHA + "\n").encode())
        result = check_commit_exists("example", "project", SHA.upper())
        self.assertEqual(result["status"], "found")
        self.assertEqual(result["commit"], SHA)

    @patch("contribution_mapper.github_reader.urlopen")
    def test_64_char_hash_is_checked(self, mock_urlopen):
        sha = "ab" * 32
        mock_urlopen.return_value = FakeResponse(sha.encode())
        self.assertEqual(check_commit_exists("example", "project", sha)["status"], "found")

    @patch("contribution_mapper.github_reader.urlopen")
    def test_not_found(self, mock_urlopen):
        for code in (404, 422):
            mock_urlopen.side_effect = http_error(code)
            result = check_commit_exists("example", "project", SHA)
            self.assertEqual(result["status"], "not_found")
            self.assertIsNone(result["proves"])
            self.assertIsNone(result["url"])

    @patch("contribution_mapper.github_reader.urlopen")
    def test_rate_limit_is_unavailable_not_not_found(self, mock_urlopen):
        for code in (403, 429):
            mock_urlopen.side_effect = http_error(code)
            result = check_commit_exists("example", "project", SHA)
            self.assertEqual(result["status"], "unavailable")
            self.assertIn("rate limit", result["reason"])

    @patch("contribution_mapper.github_reader.urlopen")
    def test_server_error_and_network_failure_are_unavailable(self, mock_urlopen):
        mock_urlopen.side_effect = http_error(500)
        self.assertEqual(check_commit_exists("example", "project", SHA)["status"], "unavailable")
        for exc in (URLError("down"), TimeoutError(), OSError("boom")):
            mock_urlopen.side_effect = exc
            result = check_commit_exists("example", "project", SHA)
            self.assertEqual(result["status"], "unavailable")
            self.assertIsNone(result["proves"])

    @patch("contribution_mapper.github_reader.urlopen")
    def test_unexpected_or_mismatched_body_is_not_found_proof(self, mock_urlopen):
        for body in (b"<html>captive portal</html>", b"0" * 40, b"", b'{"sha": "x"}'):
            mock_urlopen.return_value = FakeResponse(body)
            result = check_commit_exists("example", "project", SHA)
            self.assertEqual(result["status"], "unavailable", body)
            self.assertIsNone(result["proves"])

    @patch("contribution_mapper.github_reader.urlopen")
    def test_short_or_invalid_hash_is_skipped_without_network(self, mock_urlopen):
        for bad in ("abc123", SHA[:-1], "g" * 40, "", None, 5):
            result = check_commit_exists("example", "project", bad)
            self.assertEqual(result["status"], "skipped", bad)
        mock_urlopen.assert_not_called()

    def test_invalid_arguments_raise(self):
        with self.assertRaises(ValueError):
            check_commit_exists("", "project", SHA)
        with self.assertRaises(ValueError):
            check_commit_exists("a/b", "project", SHA)
        with self.assertRaises(ValueError):
            check_commit_exists("example", "..", SHA)
        with self.assertRaises(ValueError):
            check_commit_exists("example", "project", SHA, timeout=0)
        with self.assertRaises(ValueError):
            check_commit_exists("example", "project", SHA, timeout=True)


class RunnerCommitCheckTests(unittest.TestCase):
    def room(self):
        return {"room": "lobby", "count": 0, "first_seq": None, "last_seq": 1,
                "generation": None, "messages": [], "source": "recent"}

    @patch("contribution_mapper.runner.check_commit_exists")
    @patch("contribution_mapper.runner.read_public_room")
    @patch("contribution_mapper.runner.read_public_repository")
    def test_no_commit_means_no_check_and_no_network(self, mock_repo, mock_room, mock_commit):
        mock_repo.return_value = REPO
        mock_room.return_value = self.room()
        with tempfile.TemporaryDirectory() as d:
            report = run_mapper("example", "project", "lobby", output=str(Path(d) / "r.json"))
        self.assertEqual(report["commit_check"], {"status": "not_requested"})
        mock_commit.assert_not_called()

    @patch("contribution_mapper.runner.check_commit_exists")
    @patch("contribution_mapper.runner.read_public_room")
    @patch("contribution_mapper.runner.read_public_repository")
    def test_check_result_is_reported_and_saved(self, mock_repo, mock_room, mock_commit):
        mock_repo.return_value = REPO
        mock_room.return_value = self.room()
        mock_commit.return_value = {"status": "found", "commit": SHA}
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.json"
            report = run_mapper("example", "project", "lobby", commit=SHA, output=str(out))
            saved = json.loads(out.read_text(encoding="utf-8"))
        mock_commit.assert_called_once_with("example", "project", SHA)
        self.assertEqual(saved["commit_check"]["status"], "found")
        self.assertEqual(saved["report_version"], "1.4")
        self.assertFalse(report["interpretation"]["text_matches_prove_authorship"])

    @patch("contribution_mapper.runner.check_commit_exists")
    @patch("contribution_mapper.runner.read_public_room")
    @patch("contribution_mapper.runner.read_public_repository")
    def test_unavailable_check_does_not_abort_the_run(self, mock_repo, mock_room, mock_commit):
        mock_repo.return_value = REPO
        mock_room.return_value = self.room()
        mock_commit.return_value = {"status": "unavailable", "reason": "rate limit"}
        with tempfile.TemporaryDirectory() as d:
            report = run_mapper("example", "project", "lobby", commit=SHA,
                                output=str(Path(d) / "r.json"))
        self.assertEqual(report["commit_check"]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
