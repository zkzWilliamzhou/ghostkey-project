# Changelog

## 1.0.0

First release.

- Cross-surface key provenance: declaration, delivery, consumption, documentation.
- Verdicts: `TYPO`, `MISSING`, `GHOST`, plus `OK` counts.
- Typo attribution with edit distance 1 against consumed keys and the exact source location.
- Text, JSON (`ghostkey/1`) and SARIF 2.1.0 reports with deterministic bytes.
- Nested YAML and TOML section paths, JSON leaf keys, Dockerfile `ENV`, GitHub Actions `env:`.
- Consumption patterns for Python, JS/TS, Go, Ruby, Rust and Java.
- Hostile-tree safety: no symlink following, containment checks, `fstat` on opened descriptors, bounded reads, control-byte escaping, no values in reports.
- Eight review rounds with golden, mutation and property regression tests.
- Architecture deepening behind a frozen behavior contract.

Report schema `ghostkey/1` is frozen. Any change to output bytes requires a new schema version.
