import json
import unittest
from unittest.mock import patch

from contribution_mapper.technocore_reader import (
    TechnocoreReaderError,
    read_public_room,
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


class TechnocoreReaderTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "room": "lobby",
            "count": 1,
            "last_seq": 42,
            "messages": [{"seq": 42, "text": "Example public message"}],
        }

    @patch("contribution_mapper.technocore_reader.urlopen")
    def test_reads_valid_room_response(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(self.payload)

        result = read_public_room("lobby")

        self.assertEqual(result["room"], "lobby")
        self.assertEqual(result["last_seq"], 42)
        self.assertEqual(len(result["messages"]), 1)
        mock_urlopen.assert_called_once()

    @patch("contribution_mapper.technocore_reader.urlopen")
    def test_rejects_wrong_room(self, mock_urlopen):
        self.payload["room"] = "other"
        mock_urlopen.return_value = FakeResponse(self.payload)

        with self.assertRaises(TechnocoreReaderError):
            read_public_room("lobby")

    @patch("contribution_mapper.technocore_reader.urlopen")
    def test_rejects_boolean_count(self, mock_urlopen):
        self.payload["count"] = True
        mock_urlopen.return_value = FakeResponse(self.payload)

        with self.assertRaises(TechnocoreReaderError):
            read_public_room("lobby")

    @patch("contribution_mapper.technocore_reader.urlopen")
    def test_rejects_invalid_message_list(self, mock_urlopen):
        self.payload["messages"] = ["not an object"]
        mock_urlopen.return_value = FakeResponse(self.payload)

        with self.assertRaises(TechnocoreReaderError):
            read_public_room("lobby")

    def test_rejects_invalid_room_name(self):
        with self.assertRaises(ValueError):
            read_public_room("../private")

    def test_rejects_invalid_cursor(self):
        with self.assertRaises(ValueError):
            read_public_room("lobby", since=True)

    def test_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            read_public_room("lobby", limit=201)

    def test_rejects_non_https_base_url(self):
        with self.assertRaises(ValueError):
            read_public_room("lobby", base_url="http://example.com")


if __name__ == "__main__":
    unittest.main()
