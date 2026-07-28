import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

from envfixer.cli import main
from envfixer.model import Fingerprint


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _write_fp(self, name, **overrides):
        base = {
            "python_version": "3.11.5",
            "platform_system": "Linux",
            "platform_machine": "x86_64",
            "libc": "glibc 2.35",
            "packages": {"requests": "2.31.0", "pydantic": "2.4.2"},
            "env_var_names": ["PATH", "DATABASE_URL"],
        }
        base.update(overrides)
        path = os.path.join(self.tmp, name)
        Fingerprint.from_dict(base).save(path)
        return path

    def test_capture_to_stdout_is_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["capture"])
        self.assertEqual(rc, 0)
        json.loads(buf.getvalue())

    def test_diff_reports_and_exit_code(self):
        working = self._write_fp("working.json")
        failing = self._write_fp("failing.json",
                                 packages={"requests": "2.31.0"})  # pydantic missing
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["diff", working, failing, "--format", "json", "--fail-on", "high"])
        payload = json.loads(buf.getvalue())
        self.assertTrue(any(c["key"] == "pydantic" for c in payload["causes"]))
        self.assertEqual(rc, 1)  # high-confidence cause -> non-zero

    def test_diff_fail_on_none_is_zero(self):
        working = self._write_fp("w.json")
        failing = self._write_fp("f.json", packages={"requests": "2.31.0"})
        with redirect_stdout(io.StringIO()):
            rc = main(["diff", working, failing, "--fail-on", "none"])
        self.assertEqual(rc, 0)

    def test_diff_with_traceback(self):
        working = self._write_fp("w2.json")
        failing = self._write_fp("f2.json",
                                 packages={"requests": "2.31.1", "pydantic": "2.4.2"})
        tb = os.path.join(self.tmp, "tb.log")
        with open(tb, "w") as fh:
            fh.write("ImportError while loading requests\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["diff", working, failing, "--traceback", tb, "--format", "json"])
        payload = json.loads(buf.getvalue())
        req = next(c for c in payload["causes"] if c["key"] == "requests")
        self.assertTrue(req["mentioned_in_traceback"])

    def test_missing_file_returns_error_code(self):
        with redirect_stderr(io.StringIO()):
            rc = main(["diff", "/no/such/a.json", "/no/such/b.json"])
        self.assertEqual(rc, 2)

    def test_check_runs(self):
        with redirect_stdout(io.StringIO()):
            rc = main(["check", "--fail-on", "none"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
