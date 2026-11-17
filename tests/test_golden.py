"""Frozen behavior contract. Fails on any observable output change."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest

from tests.golden_cases import CASES, ROOT
from tests.helpers import capture_main


GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class GoldenTests(unittest.TestCase):
    def test_every_frozen_case_is_byte_identical(self):
        for name, argv in CASES:
            with self.subTest(case=name):
                path = os.path.join(GOLDEN_DIR, name + ".json")
                self.assertTrue(os.path.isfile(path), "missing golden snapshot: " + path)
                with open(path, "r", encoding="utf-8") as handle:
                    expected = json.load(handle)
                code, out, err = capture_main(argv)
                self.assertEqual(code, expected["exit_code"])
                self.assertEqual(_digest(out), expected["stdout_sha256"])
                self.assertEqual(len(out.encode("utf-8")), expected["stdout_bytes"])
                self.assertEqual(err, expected["stderr_exact"])
                self.assertEqual(expected["files_created"], [])

    def test_mutation_is_detected_by_the_oracle(self):
        with open(os.path.join(GOLDEN_DIR, "json.json"), "r", encoding="utf-8") as handle:
            expected = json.load(handle)
        holder = tempfile.mkdtemp(prefix="ghostkey-mutation-")
        try:
            mutated_root = os.path.join(holder, "demo")
            shutil.copytree(ROOT, mutated_root)
            env_path = os.path.join(mutated_root, ".env.example")
            with open(env_path, "r", encoding="utf-8") as handle:
                content = handle.read()
            with open(env_path, "w", encoding="utf-8") as handle:
                handle.write(content.replace("LOG_LEVL", "LOG_LEVXL"))
            code, out, err = capture_main([mutated_root, "--format", "json"])
            self.assertNotEqual(_digest(out), expected["stdout_sha256"])
        finally:
            shutil.rmtree(holder, ignore_errors=True)

    def test_json_and_sarif_are_parseable_and_sorted(self):
        for fmt in ("json", "sarif"):
            with self.subTest(fmt=fmt):
                code, out, err = capture_main([ROOT, "--format", fmt])
                self.assertEqual(code, 1)
                payload = json.loads(out)
                if fmt == "json":
                    self.assertEqual(payload["schema"], "ghostkey/1")
                    rank = {"TYPO": 0, "MISSING": 1, "GHOST": 2}
                    ordering = [(rank[f["verdict"]], f["normalized"])
                                for f in payload["findings"]]
                    self.assertEqual(ordering, sorted(ordering))
                else:
                    self.assertEqual(payload["version"], "2.1.0")
                    self.assertTrue(payload["runs"][0]["results"])


if __name__ == "__main__":
    unittest.main()
