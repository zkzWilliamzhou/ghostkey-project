"""Security boundary tests. The scanned tree is hostile input."""
from __future__ import annotations

import hashlib
import os
import unittest
from pathlib import Path

from ghostkey import core
from tests.helpers import capture_main, temp_tree


class PathSafetyTests(unittest.TestCase):
    def test_symlink_to_outside_root_is_not_read(self):
        import shutil
        import tempfile
        holder = tempfile.mkdtemp(prefix="ghostkey-escape-")
        base = Path(holder)
        outside = base / "outside"
        root = base / "root"
        outside.mkdir()
        root.mkdir()
        (outside / ".env").write_text("OUTSIDE_SECRET=1\n", encoding="utf-8")
        os.symlink(outside, root / "escape")
        try:
            result = core.run(core.Options(root=str(root)))
            self.assertNotIn("OUTSIDE_SECRET", {f.key for f in result.findings})
            self.assertIn("outside_root", {d.code for d in result.diagnostics})
        finally:
            shutil.rmtree(holder, ignore_errors=True)

    def test_hardlink_duplicate_inode_is_reported(self):
        root, cleanup = temp_tree({"a.env": "REAL_KEY=1\n"})
        try:
            os.link(root / "a.env", root / "b.env")
            result = core.run(core.Options(root=str(root)))
            self.assertIn("duplicate_inode", {d.code for d in result.diagnostics})
        finally:
            cleanup()

    def test_symlink_entry_is_never_followed(self):
        root, cleanup = temp_tree({"real.env": "REAL_KEY=1\n"})
        try:
            os.symlink(root / "real.env", root / "link.env")
            result = core.run(core.Options(root=str(root)))
            self.assertIn("non_regular", {d.code for d in result.diagnostics})
            self.assertEqual(result.files_scanned, 1)
        finally:
            cleanup()

    def test_fifo_is_skipped_without_blocking(self):
        root, cleanup = temp_tree({"real.env": "REAL_KEY=1\n"})
        try:
            os.mkfifo(root / "pipe.env")
            result = core.run(core.Options(root=str(root)))
            self.assertIn("non_regular", {d.code for d in result.diagnostics})
        finally:
            cleanup()

    def test_permission_error_becomes_diagnostic(self):
        from unittest import mock
        root, cleanup = temp_tree({"sub/inner.env": "INNER_KEY=1\n"})
        try:
            with mock.patch("ghostkey.core.os.scandir", side_effect=PermissionError("denied")):
                result = core.run(core.Options(root=str(root)))
            self.assertIn("unreadable_directory", {d.code for d in result.diagnostics})
            self.assertEqual(result.files_scanned, 0)
        finally:
            cleanup()


class ResourceLimitTests(unittest.TestCase):
    def test_oversized_file_is_skipped(self):
        spec = {"huge.env": "HUGE_KEY=1\n" + "#" * 5000}
        root, cleanup = temp_tree(spec)
        try:
            result = core.run(core.Options(root=str(root), max_file_bytes=100))
            self.assertIn("too_large", {d.code for d in result.diagnostics})
            self.assertNotIn("HUGE_KEY", {f.key for f in result.findings})
        finally:
            cleanup()

    def test_invalid_utf8_does_not_crash(self):
        root, cleanup = temp_tree({"bad.env": b"\x80\xffBAD_KEY=1\nGOOD_KEY=1\n"})
        try:
            result = core.run(core.Options(root=str(root)))
            self.assertIn("GOOD_KEY", {f.key for f in result.findings})
        finally:
            cleanup()

    def test_max_files_cap(self):
        spec = {"a.env": "A_KEY=1\n", "b.env": "B_KEY=1\n", "c.env": "C_KEY=1\n"}
        root, cleanup = temp_tree(spec)
        try:
            result = core.run(core.Options(root=str(root), max_files=2))
            self.assertLessEqual(result.files_scanned, 2)
            self.assertIn("max_files_reached", {d.code for d in result.diagnostics})
        finally:
            cleanup()

    def test_max_depth_cap(self):
        spec = {"a/b/c/deep.env": "DEEP_KEY=1\n"}
        root, cleanup = temp_tree(spec)
        try:
            result = core.run(core.Options(root=str(root), max_depth=1))
            self.assertNotIn("DEEP_KEY", {f.key for f in result.findings})
            self.assertIn("max_depth_exceeded", {d.code for d in result.diagnostics})
        finally:
            cleanup()

    def test_max_findings_truncates(self):
        spec = {".env.example": "".join("KEY_%03d=1\n" % i for i in range(20))}
        root, cleanup = temp_tree(spec)
        try:
            result = core.run(core.Options(root=str(root), max_findings=3))
            self.assertEqual(len(result.findings), 3)
            self.assertTrue(result.truncated)
        finally:
            cleanup()


class OutputSafetyTests(unittest.TestCase):
    def test_terminal_output_has_no_raw_escape_bytes(self):
        root, cleanup = temp_tree({"bad\x1b[31m.env": "EVIL_KEY=1\n"})
        try:
            code, out, err = capture_main([str(root), "--format", "text"])
            self.assertEqual(code, 1)
            self.assertNotIn("\x1b", out)
            self.assertNotIn("\x1b", err)
            self.assertIn("\\x1b", out)
        finally:
            cleanup()

    def test_deterministic_bytes_across_runs(self):
        from tests.golden_cases import ROOT
        for fmt in ("text", "json", "sarif"):
            first = core.render(core.run(core.Options(root=ROOT, fmt=fmt)),
                                core.Options(root=ROOT, fmt=fmt))
            second = core.render(core.run(core.Options(root=ROOT, fmt=fmt)),
                                 core.Options(root=ROOT, fmt=fmt))
            self.assertEqual(hashlib.sha256(first.encode()).hexdigest(),
                             hashlib.sha256(second.encode()).hexdigest())

    def test_paths_in_report_are_relative(self):
        from tests.golden_cases import ROOT
        result = core.run(core.Options(root=ROOT, fmt="json"))
        for finding in result.findings:
            for evidence in finding.evidence:
                self.assertFalse(evidence.file.startswith("/"))
                self.assertFalse(evidence.file.startswith(".."))


if __name__ == "__main__":
    unittest.main()
