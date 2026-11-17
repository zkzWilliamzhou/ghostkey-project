"""CLI contract tests: help, version, exit codes, streams, atomic writes."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from ghostkey import core
from tests.helpers import FIXTURE_ROOT, capture_main, temp_tree


class BrokenStream:
    def write(self, text):
        raise BrokenPipeError("closed pipe")

    def flush(self):
        pass

    def fileno(self):
        raise OSError("no descriptor")


class CliTests(unittest.TestCase):
    def test_help_goes_to_stdout_and_exits_zero(self):
        code, out, err = capture_main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("usage: ghostkey", out)
        self.assertEqual(err, "")

    def test_version_goes_to_stdout(self):
        code, out, err = capture_main(["--version"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "ghostkey " + core.VERSION)
        self.assertEqual(err, "")

    def test_unknown_argument_exits_two(self):
        code, out, err = capture_main(["--definitely-not-a-flag"])
        self.assertEqual(code, 2)
        self.assertIn("unrecognized arguments", err)
        self.assertEqual(out, "")

    def test_unresolvable_root_exits_two_with_clean_stdout(self):
        code, out, err = capture_main(["/this/path/does/not/exist/ghostkey"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("ghostkey:"))

    def test_fail_on_none_exits_zero(self):
        code, out, err = capture_main([FIXTURE_ROOT, "--format", "json", "--fail-on", "none"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertTrue(out.startswith("{"))

    def test_fail_on_ghost_only(self):
        code, _, _ = capture_main([FIXTURE_ROOT, "--fail-on", "ghost"])
        self.assertEqual(code, 1)
        root, cleanup = temp_tree({"only.env": "ONLY_ONE=1\n", "app.py": 'import os\nx=os.getenv("ONLY_ONE")\n'})
        try:
            code, _, _ = capture_main([str(root), "--fail-on", "ghost"])
            self.assertEqual(code, 0)
        finally:
            cleanup()

    def test_out_writes_file_and_keeps_stdout_empty(self):
        holder = tempfile.mkdtemp(prefix="ghostkey-out-")
        target = os.path.join(holder, "report.json")
        try:
            code, out, err = capture_main([FIXTURE_ROOT, "--format", "json", "--out", target])
            self.assertEqual(code, 1)
            self.assertEqual(out, "")
            self.assertEqual(err, "")
            self.assertTrue(os.path.isfile(target))
            with open(target, "r", encoding="utf-8") as handle:
                payload = handle.read()
            expected = core.render_json(core.run(core.Options(root=FIXTURE_ROOT, fmt="json")))
            self.assertEqual(payload, expected)
            leftovers = [name for name in os.listdir(holder) if name.startswith(".ghostkey-")]
            self.assertEqual(leftovers, [])
        finally:
            import shutil
            shutil.rmtree(holder, ignore_errors=True)

    def test_no_files_written_without_out(self):
        root, cleanup = temp_tree({"only.env": "ONLY_ONE=1\n"})
        try:
            before = sorted(os.listdir(root))
            capture_main([str(root)])
            self.assertEqual(sorted(os.listdir(root)), before)
        finally:
            cleanup()

    def test_broken_pipe_returns_one_without_traceback(self):
        from ghostkey.cli import main
        with mock.patch("sys.stdout", BrokenStream()):
            code = main([FIXTURE_ROOT, "--format", "text"])
        self.assertEqual(code, 1)

    def test_scan_error_written_to_stderr_only(self):
        code, out, err = capture_main(["/no/such/root/ghostkey", "--format", "json"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
