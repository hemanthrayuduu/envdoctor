import unittest

from envfixer import diff as d
from envfixer.diff import Difference
from envfixer.rank import rank_causes


def rank(diffs, **kw):
    return rank_causes(diffs, **kw)


class TestRank(unittest.TestCase):
    def test_missing_package_beats_patch_bump(self):
        diffs = [
            Difference(d.VERSION_MISMATCH, "requests", "2.31.0", "2.31.1"),
            Difference(d.PACKAGE_MISSING, "pydantic", "2.4.2", None),
        ]
        causes = rank(diffs)
        self.assertEqual(causes[0].difference.category, d.PACKAGE_MISSING)
        self.assertEqual(causes[0].confidence, "high")

    def test_major_beats_minor_beats_patch(self):
        major = rank([Difference(d.VERSION_MISMATCH, "a", "1.0.0", "2.0.0")])[0].score
        minor = rank([Difference(d.VERSION_MISMATCH, "a", "1.0.0", "1.1.0")])[0].score
        patch = rank([Difference(d.VERSION_MISMATCH, "a", "1.0.0", "1.0.1")])[0].score
        self.assertGreater(major, minor)
        self.assertGreater(minor, patch)

    def test_noise_env_var_dropped(self):
        causes = rank([Difference(d.ENV_VAR_MISSING, "SHLVL", "set", None)])
        self.assertEqual(causes, [])

    def test_consequential_env_var_kept_and_scored(self):
        causes = rank([Difference(d.ENV_VAR_MISSING, "DATABASE_URL", "set", None)])
        self.assertEqual(len(causes), 1)
        self.assertGreaterEqual(causes[0].score, 40)

    def test_traceback_boosts_named_package(self):
        diffs = [Difference(d.VERSION_MISMATCH, "requests", "2.31.0", "2.31.1")]
        without = rank(diffs)[0].score
        tb = "ModuleNotFoundError: No module named 'requests'"
        boosted = rank(diffs, traceback_text=tb)[0]
        self.assertGreater(boosted.score, without)
        self.assertTrue(boosted.mentioned_in_traceback)

    def test_every_cause_has_a_fix(self):
        diffs = [
            Difference(d.PACKAGE_MISSING, "pydantic", "2.4.2", None),
            Difference(d.PYTHON_VERSION, "python", "3.11.5", "3.9.1",
                       {"working_implementation": "CPython", "failing_implementation": "CPython"}),
            Difference(d.LIBC, "libc", "glibc 2.35", "musl 1.2.4"),
        ]
        for cause in rank(diffs):
            self.assertTrue(cause.fix)
            self.assertTrue(cause.rationale)

    def test_deterministic_ordering(self):
        diffs = [
            Difference(d.PACKAGE_MISSING, "b", "1.0", None),
            Difference(d.PACKAGE_MISSING, "a", "1.0", None),
        ]
        keys = [c.difference.key for c in rank(diffs)]
        self.assertEqual(keys, ["a", "b"])  # equal score -> sorted by key


if __name__ == "__main__":
    unittest.main()
