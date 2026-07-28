import json
import os
import tempfile
import unittest

from envfixer.model import Fingerprint, normalize_package_name


class TestNormalize(unittest.TestCase):
    def test_pep503_normalization(self):
        self.assertEqual(normalize_package_name("Foo_Bar.Baz"), "foo-bar-baz")
        self.assertEqual(normalize_package_name("PyYAML"), "pyyaml")


class TestFingerprint(unittest.TestCase):
    def test_capture_has_core_fields(self):
        fp = Fingerprint.capture()
        self.assertTrue(fp.python_version)
        self.assertTrue(fp.platform_system)
        self.assertIsInstance(fp.packages, dict)
        self.assertIsInstance(fp.env_var_names, list)

    def test_capture_records_env_names_not_values(self):
        os.environ["ENVDOCTOR_SECRET_XYZ"] = "super-secret-value"
        try:
            fp = Fingerprint.capture()
            blob = fp.to_json()
            self.assertIn("ENVDOCTOR_SECRET_XYZ", fp.env_var_names)
            self.assertNotIn("super-secret-value", blob)
        finally:
            del os.environ["ENVDOCTOR_SECRET_XYZ"]

    def test_roundtrip_json(self):
        fp = Fingerprint.capture()
        restored = Fingerprint.from_json(fp.to_json())
        self.assertEqual(restored.to_dict(), fp.to_dict())

    def test_from_dict_rejects_non_fingerprint(self):
        with self.assertRaises(ValueError):
            Fingerprint.from_dict({"hello": "world"})

    def test_from_dict_normalizes_package_names(self):
        fp = Fingerprint.from_dict(
            {
                "python_version": "3.11.5",
                "platform_system": "Linux",
                "packages": {"PyYAML": "6.0"},
                "env_var_names": ["PATH"],
            }
        )
        self.assertIn("pyyaml", fp.packages)
        self.assertNotIn("PyYAML", fp.packages)

    def test_save_and_load(self):
        fp = Fingerprint.capture()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "fp.json")
            fp.save(path)
            self.assertEqual(Fingerprint.load(path).to_dict(), fp.to_dict())
            # file is valid json
            with open(path) as fh:
                json.load(fh)


if __name__ == "__main__":
    unittest.main()
