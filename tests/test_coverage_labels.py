import unittest

from contribution_mapper.runner import build_retrieval_coverage


class CoverageLabelTests(unittest.TestCase):
    def data(self):
        return {"messages": [{"seq": 5, "ts": "t"}], "first_seq": 5, "generation": None}

    def test_export_does_not_label_computed_value_as_server_reported(self):
        cov = build_retrieval_coverage(self.data(), "export", 0)
        self.assertIsNone(cov["server_reported_first_seq"])

    def test_recent_keeps_server_value(self):
        cov = build_retrieval_coverage(self.data(), "recent", 0)
        self.assertEqual(cov["server_reported_first_seq"], 5)


if __name__ == "__main__":
    unittest.main()
