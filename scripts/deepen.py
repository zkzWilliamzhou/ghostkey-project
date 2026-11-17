#!/usr/bin/env python3
"""Move v1 core.py into deep modules without editing a single function body.

Reads the v1 source, extracts each top-level node with ast.get_source_segment,
and writes it verbatim into the module that owns it. core.py becomes a thin
facade. The frozen golden suite proves the observable behavior is unchanged.
"""
from __future__ import annotations

import ast
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SOURCE = os.path.join(REPO, "ghostkey", "core.py")
V1_COPY = os.path.join(REPO, "docs", "architecture", "core_v1.py")

FUTURE = "from __future__ import annotations\n"

LAYOUT = {
    "model": {
        "imports": [FUTURE, "from dataclasses import dataclass\n"],
        "names": [
            "VERSION", "SCHEMA", "DEFAULT_MAX_FILE_BYTES", "DEFAULT_MAX_FILES",
            "DEFAULT_MAX_DEPTH", "DEFAULT_MAX_FINDINGS", "MAX_KEYS_PER_FILE",
            "MAX_KEY_LEN", "MAX_EVIDENCE_PER_FINDING", "MAX_JSON_DEPTH",
            "EXCLUDED_DIRS", "AMBIENT_KEYS", "STRUCTURAL_WORDS", "VERDICT_RANK",
            "SUPPLY_SURFACES", "ScanError", "Options", "Evidence", "Finding",
            "Diagnostic", "ScanResult",
        ],
    },
    "keys": {
        "imports": [FUTURE, "import re\n", "from .model import AMBIENT_KEYS, MAX_KEY_LEN\n"],
        "names": ["CAMEL_BOUNDARY", "NON_ALNUM", "esc", "normalize",
                  "_accepted", "levenshtein"],
    },
    "walk": {
        "imports": [FUTURE, "import os\n", "import stat\n",
                    "from pathlib import Path\n",
                    "from .model import Diagnostic, EXCLUDED_DIRS, Options\n"],
        "names": ["_Skip", "_within", "_classify", "_read_bounded", "_walk"],
    },
    "surfaces": {
        "imports": [FUTURE, "import json\n", "import re\n",
                    "from .model import (Evidence, MAX_JSON_DEPTH, MAX_KEY_LEN,\n"
                    "                    MAX_KEYS_PER_FILE, Options, STRUCTURAL_WORDS)\n"],
        "names": ["SECTION_HEADER", "KEY_NAME", "DOC_KEY", "YAML_KEY",
                  "DOCKER_ENV", "CONSUMPTION_PATTERNS", "_flatten_json", "_extract"],
    },
    "analyze": {
        "imports": [FUTURE, "from typing import Iterable\n",
                    "from .keys import _accepted, levenshtein, normalize\n",
                    "from .model import (Evidence, Finding, MAX_EVIDENCE_PER_FINDING,\n"
                    "                    Options, SUPPLY_SURFACES, VERDICT_RANK)\n"],
        "names": ["_evidence_dict", "_analyze", "_representative",
                  "_trim_evidence", "_first_consumption"],
    },
    "render": {
        "imports": [FUTURE, "import json\n", "from .keys import esc\n",
                    "from .model import Finding, Options, ScanResult, SCHEMA, VERSION\n"],
        "names": ["_finding_dict", "_counts", "render_json", "render_sarif",
                  "_clip", "render_text", "render"],
    },
    "scan": {
        "imports": [FUTURE, "from pathlib import Path\n",
                    "from .analyze import _analyze, _evidence_dict\n",
                    "from .keys import normalize\n",
                    "from .surfaces import _extract\n",
                    "from .walk import _walk\n",
                    "from .model import Diagnostic, Options, ScanError, ScanResult\n"],
        "names": ["run", "decide_exit"],
    },
}

FACADE = '''"""Frozen public interface for ghostkey.

The implementation lives behind six deep modules. This module re-exports the
names callers and the golden suite depend on, so the interface does not move
when the implementation does. See ARCHITECTURE-REVIEW.html.
"""
from __future__ import annotations

import os  # noqa: F401  (kept so callers can patch os.scandir in tests)

from .model import (
    AMBIENT_KEYS, DEFAULT_MAX_DEPTH, DEFAULT_MAX_FILES,
    DEFAULT_MAX_FILE_BYTES, DEFAULT_MAX_FINDINGS, Diagnostic, Evidence,
    EXCLUDED_DIRS, Finding, MAX_EVIDENCE_PER_FINDING, MAX_JSON_DEPTH,
    MAX_KEY_LEN, MAX_KEYS_PER_FILE, Options, ScanError, ScanResult, SCHEMA,
    STRUCTURAL_WORDS, SUPPLY_SURFACES, VERSION, VERDICT_RANK,
)
from .keys import CAMEL_BOUNDARY, NON_ALNUM, _accepted, esc, levenshtein, normalize
from .walk import _classify, _read_bounded, _Skip, _walk, _within
from .surfaces import (
    CONSUMPTION_PATTERNS, DOC_KEY, DOCKER_ENV, KEY_NAME, SECTION_HEADER,
    YAML_KEY, _extract, _flatten_json,
)
from .analyze import (
    _analyze, _evidence_dict, _first_consumption, _representative,
    _trim_evidence,
)
from .render import (
    _clip, _counts, _finding_dict, render, render_json, render_sarif,
    render_text,
)
from .scan import decide_exit, run

__all__ = [name for name in dir() if not name.startswith("__")]
'''


def source_segment(source, node, lines):
    """Full source including decorators, which ast.lineno omits for classes."""
    start = node.lineno
    for decorator in getattr(node, "decorator_list", []):
        start = min(start, decorator.lineno)
    return "".join(lines[start - 1:node.end_lineno]).rstrip("\n")


def node_name(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                return target.id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def main():
    with open(SOURCE, "r", encoding="utf-8") as handle:
        source = handle.read()
    tree = ast.parse(source)

    os.makedirs(os.path.dirname(V1_COPY), exist_ok=True)
    shutil.copyfile(SOURCE, V1_COPY)

    lines = source.splitlines(keepends=True)
    segments = {}
    for node in tree.body:
        name = node_name(node)
        if name is None:
            continue
        segments[name] = source_segment(source, node, lines)

    assigned = set()
    for module, spec in LAYOUT.items():
        missing = [name for name in spec["names"] if name not in segments]
        if missing:
            print("missing source nodes for %s: %s" % (module, missing))
            return 1
        assigned.update(spec["names"])
        docstring = '"""%s module. Deep: small interface, large implementation.\n\nMoved verbatim from v1 core.py by scripts/deepen.py.\n"""\n' % module
        body = "\n\n".join(segments[name] for name in spec["names"])
        content = docstring + "".join(spec["imports"]) + "\n" + body + "\n"
        with open(os.path.join(REPO, "ghostkey", module + ".py"),
                  "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        print("wrote ghostkey/%s.py (%d nodes)" % (module, len(spec["names"])))

    with open(SOURCE, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(FACADE)
    print("wrote ghostkey/core.py facade")
    unassigned = set(segments) - assigned
    print("unassigned top-level nodes:", sorted(unassigned))
    return 0


if __name__ == "__main__":
    sys.exit(main())
