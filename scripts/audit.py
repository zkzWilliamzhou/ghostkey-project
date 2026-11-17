#!/usr/bin/env python3
"""Real, executable gates for ghostkey. No claim here is taken on trust."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from ghostkey import core  # noqa: E402
from tests.golden_cases import CASES, ROOT  # noqa: E402
from tests.helpers import capture_main  # noqa: E402

GOLDEN_DIR = os.path.join(REPO, "tests", "golden")
SOURCE_DIR = os.path.join(REPO, "ghostkey")

FORBIDDEN_CALLS = frozenset({"eval", "exec", "compile", "__import__"})
FORBIDDEN_MODULES = frozenset({
    "subprocess", "socket", "pickle", "marshal", "ctypes", "importlib",
    "yaml", "requests", "urllib", "http", "telnetlib", "ftplib", "smtplib",
})
FORBIDDEN_ATTRS = frozenset({"system", "popen"})


def forbidden():
    """AST scan of shipped source. Regex would confuse re.compile with compile()."""
    hits = []
    for filename in sorted(os.listdir(SOURCE_DIR)):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(SOURCE_DIR, filename)
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                        hits.append((filename, node.lineno, "import " + alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                if module in FORBIDDEN_MODULES:
                    hits.append((filename, node.lineno, "from " + (node.module or "")))
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALLS:
                    hits.append((filename, node.lineno, func.id + "()"))
                if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_ATTRS:
                    hits.append((filename, node.lineno, "." + func.attr + "()"))
    return hits


def determinism():
    problems = []
    for fmt in ("text", "json", "sarif"):
        options = core.Options(root=ROOT, fmt=fmt)
        first = core.render(core.run(options), options)
        second = core.render(core.run(options), options)
        if first != second:
            problems.append(fmt + ": output differs across identical runs")
    return problems


def golden():
    problems = []
    for name, argv in CASES:
        path = os.path.join(GOLDEN_DIR, name + ".json")
        if not os.path.isfile(path):
            problems.append(name + ": missing snapshot")
            continue
        with open(path, "r", encoding="utf-8") as handle:
            expected = json.load(handle)
        code, out, err = capture_main(argv)
        digest = hashlib.sha256(out.encode("utf-8")).hexdigest()
        if code != expected["exit_code"]:
            problems.append("%s: exit %d != %d" % (name, code, expected["exit_code"]))
        if digest != expected["stdout_sha256"]:
            problems.append(name + ": stdout hash changed")
        if len(out.encode("utf-8")) != expected["stdout_bytes"]:
            problems.append(name + ": stdout length changed")
        if err != expected["stderr_exact"]:
            problems.append(name + ": stderr changed")
    return problems


def suite(test_class):
    loaded = unittest.TestLoader().loadTestsFromTestCase(test_class)
    result = unittest.TestResult()
    loaded.run(result)
    problems = ["%s: %s" % (str(test).split()[0], reason.splitlines()[0])
                for test, reason in result.failures + result.errors]
    return problems


def round_checks():
    from tests import test_cli, test_core, test_golden, test_safety

    # Round 1: scope and threat model are explicit and the trust boundary is code.
    r1 = []
    adr = os.path.join(REPO, "docs", "adr", "0001-safe-scanning.md")
    if not os.path.isfile(adr):
        r1.append("ADR 0001 missing")
    for symbol in ("_walk", "_extract", "render", "run", "ScanError"):
        if not hasattr(core, symbol):
            r1.append("core." + symbol + " missing")
    defaults = (core.DEFAULT_MAX_FILE_BYTES, core.DEFAULT_MAX_FILES,
                core.DEFAULT_MAX_DEPTH, core.DEFAULT_MAX_FINDINGS)
    if any(value < 1 for value in defaults):
        r1.append("a default limit is not positive")

    # Round 5 checks that both machine formats are valid JSON on real output.
    r5 = suite(test_safety.OutputSafetyTests)
    for fmt in ("json", "sarif"):
        _, out, _ = capture_main([ROOT, "--format", fmt])
        try:
            json.loads(out)
        except ValueError as exc:
            r5.append(fmt + ": invalid JSON: " + str(exc))

    # Round 7 includes a live socket ban, not just a source scan.
    r7 = ["%s:%d %s" % hit for hit in forbidden()]
    try:
        with mock.patch("socket.socket", side_effect=AssertionError("network attempt")):
            core.run(core.Options(root=ROOT))
    except AssertionError as exc:
        r7.append("live network attempt: " + str(exc))

    # Round 9: point the tool at its own repository, audit imports, bound runtime.
    import time
    r9 = []
    started = time.monotonic()
    code, out, err = capture_main([REPO, "--format", "json", "--fail-on", "none"])
    elapsed = time.monotonic() - started
    if code != 0:
        r9.append("self-scan exit %d" % code)
    try:
        json.loads(out)
    except ValueError as exc:
        r9.append("self-scan produced invalid JSON: " + str(exc))
    if elapsed > 5.0:
        r9.append("self-scan took %.2fs" % elapsed)
    for filename in sorted(os.listdir(SOURCE_DIR)):
        if not filename.endswith(".py"):
            continue
        with open(os.path.join(SOURCE_DIR, filename), "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=filename)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in sys.stdlib_module_names:
                        r9.append("%s imports non-stdlib %s" % (filename, root))

    return [
        ("1 scope + threat model", r1),
        ("2 filesystem + path safety", suite(test_safety.PathSafetyTests)),
        ("3 resource limits", suite(test_safety.ResourceLimitTests)),
        ("4 parser correctness", suite(test_core.ParserTests)
         + suite(test_core.VerdictTests) + suite(test_core.NormalizationTests)),
        ("5 output contracts", r5),
        ("6 CLI + operational", suite(test_cli.CliTests)),
        ("7 execution isolation", r7),
        ("8 architecture regression", golden() + suite(test_golden.GoldenTests)),
        ("9 self-scan + optimization", r9),
    ]


def rounds():
    results = []
    for label, problems in round_checks():
        status = "PASS" if not problems else "FAIL"
        results.append((label, status, problems))
        print("[%s] Round %s" % (status, label))
        for problem in problems[:8]:
            print("       - " + problem)
    return results


def regression():
    from tests.test_golden import GoldenTests
    return determinism() + golden() + suite(GoldenTests)


def package():
    problems = []
    required = [
        "README.md", "LICENSE", "SECURITY.md", "CHANGELOG.md", "DESIGN.md",
        "PLAN.md", "GLOSSARY.md", "REVIEW.md", "pyproject.toml",
        "ARCHITECTURE-REVIEW.html", "ghostkey/__init__.py", "ghostkey/core.py",
        "ghostkey/cli.py", "docs/adr/0001-safe-scanning.md",
        "tests/golden/text.json", "skills/ghostkey/SKILL.md",
    ]
    for rel in required:
        if not os.path.isfile(os.path.join(REPO, rel)):
            problems.append("missing " + rel)
    with open(os.path.join(REPO, "pyproject.toml"), "r", encoding="utf-8") as handle:
        pyproject = handle.read()
    if not re.search(r'version\s*=\s*"' + re.escape(core.VERSION) + '"', pyproject):
        problems.append("pyproject version does not match core.VERSION")
    with open(os.path.join(REPO, "README.md"), "r", encoding="utf-8") as handle:
        readme = handle.read()
    if "TODO" in readme or "PLACEHOLDER" in readme:
        problems.append("README contains placeholder text")
    if core.VERSION not in readme:
        problems.append("README does not state the current version")
    code, out, _ = capture_main(["--version"])
    if code != 0 or out.strip() != "ghostkey " + core.VERSION:
        problems.append("--version output does not match core.VERSION")
    return problems


def main():
    parser = argparse.ArgumentParser(description="ghostkey audit gates")
    parser.add_argument("command", choices=(
        "forbidden", "determinism", "golden", "rounds", "regression", "package", "all"))
    args = parser.parse_args()
    commands = ["forbidden", "determinism", "golden", "rounds", "regression", "package"] \
        if args.command == "all" else [args.command]
    failed = False
    for command in commands:
        print("=== gate: %s ===" % command)
        if command == "rounds":
            results = rounds()
            failed |= any(status == "FAIL" for _, status, _ in results)
            continue
        problems = {
            "forbidden": forbidden,
            "determinism": determinism,
            "golden": golden,
            "regression": regression,
            "package": package,
        }[command]()
        if problems:
            failed = True
            print("[FAIL] %s" % command)
            for problem in problems[:20]:
                print("       - " + str(problem))
        else:
            print("[PASS] %s" % command)
    print("=== audit: %s ===" % ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
