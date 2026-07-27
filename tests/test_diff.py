import unittest

from envdoctor import diff as d
from envdoctor.diff import diff_fingerprints
from envdoctor.model import Fingerprint


def fp(**overrides):
    base = {
        "python_version": "3.11.5",
        "platform_system": "Linux",
        "platform_machine": "x86_64",
        "libc": "glibc 2.35",
        "packages": {"requests": "2.31.0", "numpy": "1.26.0"},
        "env_var_names": ["PATH", "DATABASE_URL"],
    }
    base.update(overrides)
    return Fingerprint.from_dict(base)


def categories(diffs):
    return {(x.category, x.key) for x in diffs}


class TestDiff(unittest.TestCase):
    def test_identical_has_no_diff(self):
        self.assertEqual(diff_fingerprints(fp(), fp()), [])

    def test_missing_package(self):
        failing = fp(packages={"requests": "2.31.0"})
        self.assertIn((d.PACKAGE_MISSING, "numpy"), categories(diff_fingerprints(fp(), failing)))

    def test_extra_package(self):
        failing = fp(packages={"requests": "2.31.0", "numpy": "1.26.0", "extra": "1.0"})
        self.assertIn((d.PACKAGE_EXTRA, "extra"), categories(diff_fingerprints(fp(), failing)))

    def test_version_mismatch(self):
        failing = fp(packages={"requests": "2.31.0", "numpy": "1.24.0"})
        self.assertIn((d.VERSION_MISMATCH, "numpy"), categories(diff_fingerprints(fp(), failing)))

    def test_python_version(self):
        failing = fp(python_version="3.9.18")
        self.assertIn((d.PYTHON_VERSION, "python"), categories(diff_fingerprints(fp(), failing)))

    def test_env_var_missing_direction(self):
        failing = fp(env_var_names=["PATH"])
        diffs = categories(diff_fingerprints(fp(), failing))
        self.assertIn((d.ENV_VAR_MISSING, "DATABASE_URL"), diffs)

    def test_libc_and_arch(self):
        failing = fp(libc="musl 1.2.4", platform_machine="aarch64")
        diffs = categories(diff_fingerprints(fp(), failing))
        self.assertIn((d.LIBC, "libc"), diffs)
        self.assertIn((d.PLATFORM_MACHINE, "platform_machine"), diffs)


if __name__ == "__main__":
    unittest.main()
