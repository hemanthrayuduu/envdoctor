import unittest

from envfixer.check import VERSION_CONFLICT, _requirement_specifier, analyze_dependencies
from envfixer.versions import satisfies


class TestSatisfies(unittest.TestCase):
    def test_simple_operators(self):
        self.assertTrue(satisfies("3.0.1", ">=3.0"))
        self.assertFalse(satisfies("2.3.7", ">=3.0"))
        self.assertTrue(satisfies("1.2.3", "==1.2.3"))
        self.assertFalse(satisfies("1.2.4", "==1.2.3"))
        self.assertTrue(satisfies("1.2.4", "!=1.2.3"))
        self.assertTrue(satisfies("1.0.0", "<2.0"))
        self.assertFalse(satisfies("2.0.0", "<2.0"))

    def test_specifier_sets(self):
        self.assertTrue(satisfies("2.5.0", ">=2.0,<3.0"))
        self.assertFalse(satisfies("3.1.0", ">=2.0,<3.0"))

    def test_wildcards(self):
        self.assertTrue(satisfies("1.4.9", "==1.4.*"))
        self.assertFalse(satisfies("1.5.0", "==1.4.*"))
        self.assertTrue(satisfies("1.5.0", "!=1.4.*"))

    def test_compatible_release(self):
        self.assertTrue(satisfies("1.4.5", "~=1.4.2"))
        self.assertFalse(satisfies("1.5.0", "~=1.4.2"))
        self.assertFalse(satisfies("1.4.1", "~=1.4.2"))

    def test_unknown_is_none_not_a_guess(self):
        # Pre-release versions and unparseable specifiers must not be judged.
        self.assertIsNone(satisfies("3.0.0rc1", ">=3.0"))
        self.assertIsNone(satisfies("1.0.0", "not-a-specifier"))
        self.assertIsNone(satisfies("1.0.0", ""))

    def test_padding(self):
        self.assertTrue(satisfies("3", ">=3.0.0"))
        self.assertTrue(satisfies("3.0", "==3.0.0"))


class TestRequirementSpecifier(unittest.TestCase):
    def test_extracts(self):
        self.assertEqual(_requirement_specifier("werkzeug>=3.0"), ">=3.0")
        self.assertEqual(_requirement_specifier("requests[security]>=2.0,<3"), ">=2.0,<3")
        self.assertEqual(_requirement_specifier("Werkzeug (>=3.0)"), ">=3.0")
        self.assertEqual(_requirement_specifier("bare-package"), "")
        self.assertEqual(_requirement_specifier("pkg @ https://x/y.whl"), "")


class TestVersionConflicts(unittest.TestCase):
    def test_flags_conflict(self):
        findings = analyze_dependencies(
            requirements=[("flask", "werkzeug>=3.0")],
            installed={"flask": "3.0.0", "werkzeug": "2.3.7"},
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, VERSION_CONFLICT)
        self.assertEqual(findings[0].key, "werkzeug")
        self.assertIn("2.3.7", findings[0].message)
        self.assertTrue(findings[0].fix)

    def test_no_finding_when_satisfied(self):
        findings = analyze_dependencies(
            requirements=[("flask", "werkzeug>=3.0")],
            installed={"flask": "3.0.0", "werkzeug": "3.0.1"},
        )
        self.assertEqual(findings, [])

    def test_no_finding_when_undecidable(self):
        findings = analyze_dependencies(
            requirements=[("flask", "werkzeug>=3.0")],
            installed={"flask": "3.0.0", "werkzeug": "3.0.0rc1"},
        )
        self.assertEqual(findings, [])

    def test_conflict_outranks_missing(self):
        findings = analyze_dependencies(
            requirements=[("a", "gone>=1.0"), ("b", "old>=3.0")],
            installed={"a": "1.0", "b": "1.0", "old": "2.0"},
        )
        self.assertEqual(findings[0].category, VERSION_CONFLICT)

    def test_set_input_still_works_missing_only(self):
        # Backwards compatible: a plain set disables conflict detection.
        findings = analyze_dependencies(
            requirements=[("flask", "werkzeug>=3.0")],
            installed={"flask", "werkzeug"},
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
