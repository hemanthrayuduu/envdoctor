import json
import unittest

from envfixer import diff as d
from envfixer.diff import Difference
from envfixer.rank import rank_causes
from envfixer.report import exit_code, render


def sample_causes():
    diffs = [
        Difference(d.PACKAGE_MISSING, "pydantic", "2.4.2", None),
        Difference(d.VERSION_MISMATCH, "numpy", "1.26.0", "1.24.0"),
    ]
    return rank_causes(diffs)


class TestReport(unittest.TestCase):
    def test_human_mentions_fix_and_key(self):
        out = render(sample_causes(), "diagnosis", "human")
        self.assertIn("pydantic", out)
        self.assertIn("fix:", out)

    def test_json_is_valid(self):
        out = render(sample_causes(), "diagnosis", "json")
        parsed = json.loads(out)
        self.assertEqual(parsed["title"], "diagnosis")
        self.assertTrue(parsed["causes"])

    def test_markdown_table(self):
        out = render(sample_causes(), "diagnosis", "markdown")
        self.assertIn("| # |", out)
        self.assertIn("pydantic", out)

    def test_sarif_is_valid_and_has_results(self):
        out = render(sample_causes(), "diagnosis", "sarif")
        parsed = json.loads(out)
        self.assertEqual(parsed["version"], "2.1.0")
        self.assertEqual(parsed["runs"][0]["tool"]["driver"]["name"], "EnvFixer")
        self.assertTrue(parsed["runs"][0]["results"])

    def test_empty_human_output(self):
        out = render([], "diagnosis", "human")
        self.assertIn("No likely causes", out)

    def test_exit_code_policy(self):
        causes = sample_causes()  # contains a high-confidence missing package
        self.assertEqual(exit_code(causes, "high"), 1)
        self.assertEqual(exit_code(causes, "none"), 0)
        self.assertEqual(exit_code([], "low"), 0)


if __name__ == "__main__":
    unittest.main()
