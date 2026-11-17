# ADR 0001: the scanned tree is hostile input

Status: accepted. Later architecture reviews do not reopen this decision.

## Context

ghostkey runs against repositories the user does not control. Filenames, symlink targets, file types, byte contents and encodings are attacker-controlled in the worst case. The tool has to be safe to point at a checkout of someone else's code.

## Decision

The scanner is a parser, not a runtime.

1. Resolve the root once with `Path.resolve(strict=True)` and require a directory.
2. Never follow symlinks. `os.scandir` entries are stat'ed with `follow_symlinks=False`; anything that is not `S_ISREG` or a real directory is skipped with a diagnostic.
3. Verify containment with `os.path.commonpath` before any read.
4. Track `(st_dev, st_ino)` for directories and files to stop loops and duplicate work.
5. Re-check the opened descriptor with `os.fstat` so a swapped path cannot turn a stat'ed regular file into a device read.
6. Bound file size, file count, depth, keys per file, findings and output. Read bytes, decode with `errors='replace'`, never feed replacement characters back into a matcher.
7. Discard values at the parser boundary. No value reaches a finding, report or diagnostic.
8. Escape control characters, ANSI sequences and bidi overrides in terminal output. JSON uses `ensure_ascii=True`.
9. Never call `eval`, `exec`, `compile`, `__import__`, `importlib`, `pickle`, `marshal`, `subprocess`, `socket`, `ctypes` or a YAML loader. No network, no writes into the scanned tree.
10. Sort everything. No timestamps, absolute paths, or iteration order in reports.

## Consequences

Some correct usage is invisible: dynamically constructed keys, shell expansion, custom config grammars. Those become diagnostics or honest silence, never guessed verdicts. Static parsers are conservative by design.

The behavior contract is frozen at `ghostkey.cli.main(argv)` and `ghostkey.core.run(options)`. Any future change to output bytes requires a new schema version and a migration test, not a silent tweak.

## Alternatives rejected

- Runtime instrumentation: executes untrusted code, needs the application to run, sees only exercised paths.
- Full YAML/TOML libraries: adds dependencies and a larger parsing attack surface for a job that needs only key names.
- Auto-fixing keys: writes into a repository the tool does not own.
