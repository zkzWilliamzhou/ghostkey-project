"""Frozen behavior cases. Used by make_golden.py, audit.py and test_golden.py."""
import os

ROOT = os.path.join(os.path.dirname(__file__), "fixtures", "demo")

CASES = [
    ("text", [ROOT, "--format", "text"]),
    ("json", [ROOT, "--format", "json"]),
    ("sarif", [ROOT, "--format", "sarif"]),
    ("json_fail_none", [ROOT, "--format", "json", "--fail-on", "none"]),
    ("json_exact", [ROOT, "--format", "json", "--exact"]),
    ("text_show_ok", [ROOT, "--format", "text", "--show-ok"]),
]
