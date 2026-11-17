"""Shared test helpers. Standard library only."""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

FIXTURE_ROOT = os.path.join(os.path.dirname(__file__), "fixtures", "demo")


def capture_main(argv):
    """Run cli.main with captured streams. Returns (code, stdout, stderr)."""
    from ghostkey.cli import main

    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 0
    return code, out.getvalue(), err.getvalue()


def temp_tree(spec):
    """Build a tree from {relative_path: contents}. Returns (root, cleanup)."""
    holder = tempfile.mkdtemp(prefix="ghostkey-test-")
    root = Path(holder)
    for rel, content in spec.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")
    return root, lambda: __import__("shutil").rmtree(holder, ignore_errors=True)
