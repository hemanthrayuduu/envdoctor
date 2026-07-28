import unittest

from envfixer.versions import VersionGap, parse_release, version_gap


class TestVersions(unittest.TestCase):
    def test_parse_release(self):
        self.assertEqual(parse_release("1.2.3"), (1, 2, 3))
        self.assertEqual(parse_release("2.0.7"), (2, 0, 7))
        self.assertEqual(parse_release("2023.7.22"), (2023, 7, 22))
        self.assertIsNone(parse_release("not-a-version"))
        self.assertIsNone(parse_release(""))

    def test_gap_classification(self):
        self.assertEqual(version_gap("1.0.0", "2.0.0"), VersionGap.MAJOR)
        self.assertEqual(version_gap("1.24.0", "1.26.0"), VersionGap.MINOR)
        self.assertEqual(version_gap("2.31.0", "2.31.1"), VersionGap.PATCH)
        self.assertEqual(version_gap("1.2.3", "1.2.3"), VersionGap.NONE)

    def test_gap_ordering_reflects_blast_radius(self):
        self.assertGreater(VersionGap.MAJOR, VersionGap.MINOR)
        self.assertGreater(VersionGap.MINOR, VersionGap.PATCH)

    def test_unparseable_gap(self):
        self.assertEqual(version_gap("abc", "def"), VersionGap.UNKNOWN)
        self.assertEqual(version_gap("abc", "abc"), VersionGap.NONE)

    def test_uneven_length(self):
        self.assertEqual(version_gap("1.2", "1.2.0"), VersionGap.NONE)
        self.assertEqual(version_gap("1.2", "1.2.1"), VersionGap.PATCH)


if __name__ == "__main__":
    unittest.main()
