import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from contribution_mapper.runner import run_mapper


class RunnerTests(unittest.TestCase):
    @patch("contribution_mapper.runner.read_public_room")
    @patch("contribution_mapper.runner.read_public_repository")
    def test_generates_local_report(
        self, mock_repository, mock_room
    ):
        mock_repository.return_value = {
            "full_name": "example/project",
            "html_url": "https://github.com/example/project",
            "description": "Example project",
        }
        mock_room.return_value = {
            "room": "lobby",
            "count": 1,
            "last_seq": 42,
            "messages": [
                {
                    "from": "did:example:123",
                    "seq": 42,
                    "text": "Project: https://github.com/example/project",
                }
            ],
            "source": "https://technocore.chat/r/lobby",
        }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            report = run_mapper(
                "example",
                "project",
                "lobby",
                output=str(output),
            )

            saved = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(saved["repository"]["full_name"], "example/project")
        self.assertEqual(report["technocore_source"]["last_seq"], 42)
        self.assertEqual(report["evidence"]["record_count"], 1)
        self.assertEqual(
            report["evidence"]["status_counts"]["unverified"], 1
        )
        mock_repository.assert_called_once_with("example", "project")
        mock_room.assert_called_once_with("lobby")

    @patch("contribution_mapper.runner.read_public_room")
    @patch("contribution_mapper.runner.read_public_repository")
    def test_does_not_write_report_if_source_read_fails(
        self, mock_repository, mock_room
    ):
        mock_repository.return_value = {
            "full_name": "example/project",
            "html_url": "https://github.com/example/project",
        }
        mock_room.side_effect = RuntimeError("simulated source failure")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            with self.assertRaises(RuntimeError):
                run_mapper(
                    "example", "project", "lobby", output=str(output)
                )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
