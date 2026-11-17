---
name: ghostkey
description: Find configuration keys that are declared but never read, read but never declared, or one character away from the key the code uses. Use when debugging silent config failures, auditing environment variables before a deploy, or adding a config-drift gate to CI. Do not use for secret scanning, schema validation, or fixing config values.
license: MIT
---

# ghostkey

Run `python3 -m ghostkey <repo-root>` from the ghostkey checkout, or `ghostkey <repo-root>` after install. It needs Python 3.10+ and no third-party packages. It reads key names only and never prints values.

## Interpret the report

- `TYPO`: a declared key is one edit away from a key the source reads. Fix the declaration first. The report names the consumed key and its `file:line`.
- `MISSING`: source reads a key nobody declared or delivered. Add it to `.env.example` or the deployment manifest, or fix the source.
- `GHOST`: a key is declared or delivered but no code reads it. Check for a rename before deleting it.
- `OK`: supply and demand both exist. Visible with `--show-ok`.

A `GHOST` can be a false positive when the application builds key names at runtime. Check the evidence file and line before changing anything. Use `--ignore KEY` for a known dynamic key, and `--exact` when case and separator folding causes a wrong join.

## CI usage

```sh
ghostkey . --format sarif --out ghostkey.sarif
ghostkey . --fail-on typo
```

Exit codes: 0 clean, 1 findings, 2 bad arguments or scan error, 130 interrupted. Reports are deterministic, so a byte diff between two runs is a real change.

## Boundaries

Never paste report values into a chat or a log, because the tool deliberately discards values and only emits key names. Never ask it to auto-fix a key. It does not execute repository code and does not use the network. Review `SECURITY.md` before changing the scanner.
