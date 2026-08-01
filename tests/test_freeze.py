import unittest

from envfixer import diff as d
from envfixer.diff import diff_fingerprints
from envfixer.model import UNKNOWN, Fingerprint, is_unknown, parse_freeze
from envfixer.rank import rank_causes

FREEZE = """\
# a comment
requests==2.31.0
PyYAML==6.0.1
Flask[async]==3.0.0
-e git+https://github.com/x/y.git#egg=local
some-pkg @ https://example.com/pkg.whl
unpinned-package
ranged>=1.0
"""


class TestParseFreeze(unittest.TestCase):
    def test_parses_exact_pins_only(self):
        packages = parse_freeze(FREEZE)
        self.assertEqual(packages["requests"], "2.31.0")
        self.assertEqual(packages["pyyaml"], "6.0.1")  # PEP 503 normalized
        self.assertEqual(packages["flask"], "3.0.0")   # extras stripped

    def test_skips_non_pinned_entries(self):
        packages = parse_freeze(FREEZE)
        for skipped in ("local", "some-pkg", "unpinned-package", "ranged"):
            self.assertNotIn(skipped, packages)

    def test_empty_input(self):
        self.assertEqual(parse_freeze(""), {})


class TestFromFreeze(unittest.TestCase):
    def test_unknown_fields_are_marked_unknown(self):
        fp = Fingerprint.from_freeze("requests==2.31.0")
        self.assertEqual(fp.source, "freeze")
        self.assertTrue(is_unknown(fp.python_version))
        self.assertTrue(is_unknown(fp.platform_system))
        self.assertIsNone(fp.env_var_names)

    def test_supplied_metadata_is_kept(self):
        fp = Fingerprint.from_freeze(
            "requests==2.31.0", python_version="3.9.18", platform_system="Linux"
        )
        self.assertEqual(fp.python_version, "3.9.18")
        self.assertEqual(fp.platform_system, "Linux")

    def test_roundtrip_json(self):
        fp = Fingerprint.from_freeze("requests==2.31.0")
        self.assertEqual(Fingerprint.from_json(fp.to_json()).to_dict(), fp.to_dict())


class TestPartialDiffSafety(unittest.TestCase):
    """A partial fingerprint must never manufacture differences."""

    def setUp(self):
        self.full = Fingerprint.from_dict(
            {
                "python_version": "3.11.5",
                "python_implementation": "CPython",
                "platform_system": "Linux",
                "platform_machine": "x86_64",
                "libc": "glibc 2.35",
                "timezone": "UTC+00:00",
                "locale_encoding": "UTF-8",
                "packages": {"requests": "2.31.0", "pydantic": "2.4.2"},
                "env_var_names": ["PATH", "DATABASE_URL"],
            }
        )

    def test_only_real_package_difference_surfaces(self):
        failing = Fingerprint.from_freeze("requests==2.31.0")  # pydantic missing
        diffs = diff_fingerprints(self.full, failing)
        categories = {x.category for x in diffs}
        self.assertIn(d.PACKAGE_MISSING, categories)
        # None of these are knowable from a freeze dump -> must not be reported.
        for bogus in (d.PYTHON_VERSION, d.PLATFORM_SYSTEM, d.PLATFORM_MACHINE,
                      d.LIBC, d.TIMEZONE, d.LOCALE,
                      d.ENV_VAR_MISSING, d.ENV_VAR_EXTRA):
            self.assertNotIn(bogus, categories, f"{bogus} fabricated from unknown data")

    def test_true_cause_still_ranks_first(self):
        failing = Fingerprint.from_freeze("requests==2.31.0")
        causes = rank_causes(diff_fingerprints(self.full, failing))
        self.assertEqual(causes[0].difference.key, "pydantic")

    def test_freeze_omitted_bootstrap_packages_are_not_flagged(self):
        # pip freeze omits pip/setuptools/wheel, and envfixer is the tool
        # itself — none of these are real drift.
        working = Fingerprint.from_dict(
            {
                "python_version": "3.11.5",
                "platform_system": "Linux",
                "packages": {
                    "pip": "24.0", "setuptools": "69.0.3", "wheel": "0.42.0",
                    "envfixer": "0.2.0", "requests": "2.31.0", "pydantic": "2.4.2",
                },
                "env_var_names": ["PATH"],
            }
        )
        failing = Fingerprint.from_freeze("requests==2.31.0")
        keys = {x.key for x in diff_fingerprints(working, failing)}
        self.assertEqual(keys, {"pydantic"})

    def test_bootstrap_still_compared_between_live_captures(self):
        def live(packages):
            return Fingerprint.from_dict({
                "python_version": "3.11.5", "platform_system": "Linux",
                "packages": packages, "env_var_names": ["PATH"],
            })
        keys = {x.key for x in diff_fingerprints(
            live({"setuptools": "69.0.3"}), live({}))}
        self.assertIn("setuptools", keys)

    def test_schema_v1_fingerprint_has_no_tz_locale_diff(self):
        legacy = Fingerprint.from_dict(
            {
                "python_version": "3.11.5",
                "platform_system": "Linux",
                "platform_machine": "x86_64",
                "libc": "glibc 2.35",
                "packages": {"requests": "2.31.0", "pydantic": "2.4.2"},
                "env_var_names": ["PATH", "DATABASE_URL"],
                "schema_version": 1,
            }
        )
        categories = {x.category for x in diff_fingerprints(self.full, legacy)}
        self.assertNotIn(d.TIMEZONE, categories)
        self.assertNotIn(d.LOCALE, categories)


if __name__ == "__main__":
    unittest.main()
