import json
import unittest
from unittest.mock import patch

from contribution_mapper.github_reader import (
    GitHubReaderError,
    read_public_repository,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class GitHubReaderTests(unittest.TestCase):
    @patch("contribution_mapper.github_reader.urlopen")
    def test_reads_repository_metadata(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse({
            "full_name": "example/project",
            "html_url": "https://github.com/example/project",
            "description": "Example project",
            "default_branch": "main",
            "stargazers_count": 12,
            "forks_count": 3,
            "open_issues_count": 1,
            "license": {"spdx_id": "MIT"},
        })

        result = read_public_repository("example", "project")

        self.assertEqual(result["full_name"], "example/project")
        self.assertEqual(result["stars"], 12)
        self.assertEqual(result["license_spdx_id"], "MIT")
        self.assertEqual(result["source"], "GitHub public API")
        mock_urlopen.assert_called_once()

    def test_rejects_empty_owner(self):
        with self.assertRaises(ValueError):
            read_public_repository("", "project")

    def test_rejects_path_injection(self):
        with self.assertRaises(ValueError):
            read_public_repository("example/other", "project")

    def test_rejects_nonpositive_timeout(self):
        with self.assertRaises(ValueError):
            read_public_repository("example", "project", timeout=0)

    @patch("contribution_mapper.github_reader.urlopen")
    def test_rejects_incomplete_response(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse({"description": "Incomplete"})

        with self.assertRaises(GitHubReaderError):
            read_public_repository("example", "project")


if __name__ == "__main__":
    unittest.main()
