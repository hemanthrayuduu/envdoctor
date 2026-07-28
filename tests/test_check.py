import unittest

from envfixer.check import (
    MISSING_DEPENDENCY,
    _requirement_name,
    analyze_dependencies,
)


class TestRequirementName(unittest.TestCase):
    def test_extracts_name(self):
        self.assertEqual(_requirement_name("requests>=2.0"), "requests")
        self.assertEqual(_requirement_name("PyYAML (>=5.1)"), "pyyaml")
        self.assertEqual(_requirement_name("importlib-metadata ; python_version < '3.8'"),
                         "importlib-metadata")
        self.assertIsNone(_requirement_name("!!!"))


class TestAnalyzeDependencies(unittest.TestCase):
    def test_flags_missing_dependency(self):
        findings = analyze_dependencies(
            requirements=[("flask", "werkzeug>=3.0")],
            installed={"flask"},
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, MISSING_DEPENDENCY)
        self.assertEqual(findings[0].key, "werkzeug")
        self.assertTrue(findings[0].fix)

    def test_no_finding_when_installed(self):
        findings = analyze_dependencies(
            requirements=[("flask", "werkzeug>=3.0")],
            installed={"flask", "werkzeug"},
        )
        self.assertEqual(findings, [])

    def test_deduplicates(self):
        findings = analyze_dependencies(
            requirements=[("a", "shared>=1"), ("b", "shared>=2")],
            installed=set(),
        )
        self.assertEqual(len(findings), 1)


if __name__ == "__main__":
    unittest.main()
