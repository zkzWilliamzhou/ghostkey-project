"""Unit tests for normalization, surface parsers and verdicts."""
from __future__ import annotations

import json
import unittest

from ghostkey import core
from tests.helpers import FIXTURE_ROOT, capture_main, temp_tree


class NormalizationTests(unittest.TestCase):
    def test_folds_dots_dashes_and_case(self):
        self.assertEqual(core.normalize("db.host"), "DB_HOST")
        self.assertEqual(core.normalize("DB_HOST"), "DB_HOST")
        self.assertEqual(core.normalize("db-host"), "DB_HOST")
        self.assertEqual(core.normalize("timeoutMs"), "TIMEOUT_MS")

    def test_exact_mode_keeps_raw(self):
        self.assertEqual(core.normalize("db.host", exact=True), "db.host")
        self.assertNotEqual(core.normalize("db.host", exact=True), "DB_HOST")

    def test_levenshtein_bounded(self):
        self.assertEqual(core.levenshtein("LOG_LEVL", "LOG_LEVEL", 1), 1)
        self.assertEqual(core.levenshtein("DB_HOST", "DB_PORT", 1), 2)
        self.assertEqual(core.levenshtein("SAME", "SAME", 1), 0)

    def test_escape_removes_terminal_controls(self):
        self.assertNotIn("\x1b", core.esc("a\x1b[31mb"))
        self.assertIn("\\x1b", core.esc("a\x1b[31mb"))
        self.assertIn("\\u202e", core.esc("a\u202eb"))


class ParserTests(unittest.TestCase):
    def opts(self):
        return core.Options(root=".", exact=False)

    def test_env_export_and_comments(self):
        ev = core._extract("env", ".env.example",
                           "# note\nexport DB_HOST=localhost\nBAD KEY=x\n", self.opts())
        self.assertEqual([(e.surface, e.raw, e.line) for e in ev],
                         [("declaration", "DB_HOST", 2)])

    def test_json_flatten_produces_dotted_keys(self):
        ev = core._extract("json", "app.json",
                           '{"db": {"host": "x"}, "retry": 3}', self.opts())
        self.assertIn("db.host", [e.raw for e in ev])
        self.assertIn("retry", [e.raw for e in ev])

    def test_yaml_nested_keys_keep_parent_path(self):
        ev = core._extract("yaml", "config.yaml",
                           "db:\n  host: localhost\n  port: 5432\n", self.opts())
        self.assertEqual([e.raw for e in ev], ["db.host", "db.port"])

    def test_toml_section_prefix(self):
        ev = core._extract("toml", "config.toml",
                           "[server]\nhost = \"0.0.0.0\"\n", self.opts())
        self.assertEqual([e.raw for e in ev], ["server.host"])

    def test_workflow_env_keys_are_plain(self):
        ev = core._extract("workflow", ".github/workflows/ci.yml",
                           "jobs:\n  build:\n    env:\n      LOG_LEVEL: info\n", self.opts())
        self.assertEqual([e.raw for e in ev], ["LOG_LEVEL"])

    def test_docker_env_only(self):
        ev = core._extract("docker", "Dockerfile",
                           "ENV APP_MODE=prod OTHER=1\nARG BASE_IMAGE=python\n", self.opts())
        self.assertEqual([e.raw for e in ev], ["APP_MODE", "OTHER"])
        self.assertTrue(all(e.surface == "delivery" for e in ev))

    def test_markdown_backticks_are_documentation(self):
        ev = core._extract("doc", "README.md",
                           "Set `DATABASE_URL` before running.\n", self.opts())
        self.assertEqual([(e.surface, e.raw) for e in ev],
                         [("documentation", "DATABASE_URL")])

    def test_consumption_patterns_across_languages(self):
        samples = [
            ("app.py", 'os.getenv("PY_KEY")', "PY_KEY"),
            ("app.py", 'os.environ["PY_KEY2"]', "PY_KEY2"),
            ("a.js", "process.env.JS_KEY", "JS_KEY"),
            ("a.ts", "process.env['TS_KEY']", "TS_KEY"),
            ("a.js", "Deno.env.get('DENO_KEY')", "DENO_KEY"),
            ("a.go", 'os.Getenv("GO_KEY")', "GO_KEY"),
            ("a.rb", 'ENV.fetch("RB_KEY")', "RB_KEY"),
            ("a.rs", 'env::var("RS_KEY")', "RS_KEY"),
            ("a.java", 'System.getenv("JAVA_KEY")', "JAVA_KEY"),
        ]
        for filename, line, expected in samples:
            with self.subTest(line=line):
                ev = core._extract("source", filename, line + "\n", self.opts())
                self.assertIn(expected, [e.raw for e in ev])

    def test_values_never_appear_in_evidence(self):
        ev = core._extract("env", ".env.example", "API_TOKEN=supersecretvalue12345\n", self.opts())
        self.assertEqual([(e.surface, e.raw) for e in ev], [("declaration", "API_TOKEN")])
        self.assertNotIn("supersecretvalue12345", repr(ev))


class VerdictTests(unittest.TestCase):
    def test_all_four_verdicts(self):
        spec = {
            ".env.example": "DATABASE_URL=x\nLOG_LEVL=debug\nTIMEOUT_MS=5000\n",
            "src/app.py": 'import os\ndb=os.getenv("DATABASE_URL")\nlvl=os.getenv("LOG_LEVEL")\nreg=os.getenv("AWS_REGION")\n',
        }
        root, cleanup = temp_tree(spec)
        try:
            result = core.run(core.Options(root=str(root), fmt="json"))
            verdicts = {f.key: f.verdict for f in result.findings}
            self.assertEqual(verdicts.get("LOG_LEVL"), "TYPO")
            self.assertEqual(verdicts.get("TIMEOUT_MS"), "GHOST")
            self.assertEqual(verdicts.get("AWS_REGION"), "MISSING")
            self.assertEqual(result.ok_count, 1)
            typo = next(f for f in result.findings if f.verdict == "TYPO")
            self.assertEqual(typo.suggestion, "LOG_LEVEL")
            self.assertIn("src/app.py", typo.suggestion_where)
        finally:
            cleanup()

    def test_no_false_typo_for_two_substitutions(self):
        spec = {
            ".env.example": "DB_HOST=localhost\nDB_PORT=5432\n",
            "src/app.py": 'import os\nhost=os.getenv("DB_HOST")\n',
        }
        root, cleanup = temp_tree(spec)
        try:
            result = core.run(core.Options(root=str(root)))
            self.assertNotIn("TYPO", [f.verdict for f in result.findings])
        finally:
            cleanup()

    def test_ignore_and_ambient_keys(self):
        spec = {".env.example": "PATH=/bin\nMY_IGNORED_KEY=x\nREAL_KEY=y\n"}
        root, cleanup = temp_tree(spec)
        try:
            result = core.run(core.Options(root=str(root), ignores=("MY_IGNORED_KEY",)))
            keys = {f.key for f in result.findings}
            self.assertNotIn("PATH", keys)
            self.assertNotIn("MY_IGNORED_KEY", keys)
            self.assertIn("REAL_KEY", keys)
        finally:
            cleanup()

    def test_secret_value_never_in_report(self):
        secret = "sk_live_DO_NOT_LEAK_98765"
        spec = {".env.example": "API_TOKEN=" + secret + "\n",
                "src/app.py": 'import os\nt=os.getenv("OTHER_KEY")\n'}
        root, cleanup = temp_tree(spec)
        try:
            for fmt in ("text", "json", "sarif"):
                code, out, err = capture_main([str(root), "--format", fmt])
                self.assertEqual(code, 1)
                self.assertNotIn(secret, out)
                self.assertNotIn(secret, err)
        finally:
            cleanup()

    def test_fixture_report_is_valid_json(self):
        result = core.run(core.Options(root=FIXTURE_ROOT, fmt="json"))
        payload = json.loads(core.render_json(result))
        self.assertEqual(payload["schema"], "ghostkey/1")
        self.assertGreaterEqual(payload["scan"]["typo"], 1)
        self.assertGreaterEqual(payload["scan"]["missing"], 1)
        self.assertGreaterEqual(payload["scan"]["ghost"], 1)
        self.assertGreaterEqual(payload["scan"]["ok"], 1)


if __name__ == "__main__":
    unittest.main()
