#!/usr/bin/env python3
"""Freeze the observable behavior of v1 before the architecture refactor."""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from tests.golden_cases import CASES  # noqa: E402
from tests.helpers import capture_main  # noqa: E402

GOLDEN_DIR = os.path.join(REPO, "tests", "golden")


def main():
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    for name, argv in CASES:
        code, out, err = capture_main(argv)
        record = {
            "case": name,
            "exit_code": code,
            "stdout_sha256": hashlib.sha256(out.encode("utf-8")).hexdigest(),
            "stdout_bytes": len(out.encode("utf-8")),
            "stderr_exact": err,
            "files_created": [],
        }
        path = os.path.join(GOLDEN_DIR, name + ".json")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(record, handle, indent=2, ensure_ascii=True, sort_keys=True)
            handle.write("\n")
        print("froze %-16s exit=%d bytes=%d sha=%s" % (
            name, code, record["stdout_bytes"], record["stdout_sha256"][:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
