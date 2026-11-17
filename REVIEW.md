# Review log

Nine rounds. Every round ran a command and I read its output before writing a verdict. Defects are listed with the evidence that exposed them, the fix, and the regression test that now fails if the fix is removed. Nothing in this file is a claim that a command "should" pass.

Command used throughout, from the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/audit.py all
python3 scripts/audit.py rounds
```

Final state: 44 tests, 0 failures. All audit gates PASS. Six golden cases byte-identical after the architecture refactor.

## Round 1. Scope and threat model

Focus: enumerate every input and output sink, and confirm the trust boundary is code, not a comment.

Findings:
- `docs/adr/0001-safe-scanning.md` was missing. The first write did not land. Recreated it and added a gate that fails Round 1 if the file is absent.
- Confirmed the input list: filenames, symlink targets, file types, byte contents, encodings, key names. Output list: stdout, stderr, `--out` file, exit code, JSON and SARIF renderers.
- The scanner calls no `eval`, `exec`, `subprocess`, `socket`, `pickle` or YAML loader. A naive grep would have flagged `re.compile`; Round 7 replaced it with an AST check.

Verdict: PASS. `python3 scripts/audit.py rounds` reports `[PASS] Round 1 scope + threat model`.

## Round 2. Filesystem and path safety

Focus: symlink escapes, symlink loops, hardlinks, special files, TOCTOU, permissions, containment.

Evidence: a smoke scan on a tree containing `outside/.env` and `root/escape -> ../outside` produced `outside_root` and no `OUTSIDE_SECRET` finding. A FIFO, a symlinked file, and two hardlinks to one inode each produced bounded diagnostics rather than a hang or a double read.

Six tests in `test_safety.PathSafetyTests` pass. One test I first wrote used `self.assertTrue(True)` and proved nothing. I replaced it with a deterministic `mock.patch` of `os.scandir` raising `PermissionError` and asserted `unreadable_directory` plus zero files scanned. That was my own fake test and I rejected it.

Verdict: PASS.

## Round 3. Resource limits

Focus: file size, file count, depth, keys per file, findings, invalid UTF-8, decoding.

Evidence: a 5 KB file with `--max-file-bytes 100` produced `too_large` and no key. A file containing `\x80\xff` decoded with replacement and did not crash. `--max-files 2`, `--max-depth 1` and `--max-findings 3` each produced the expected cap and diagnostic. `_read_bounded` re-checks the opened descriptor with `os.fstat` before reading, which closes the stat/open swap.

Five tests in `test_safety.ResourceLimitTests` pass.

Verdict: PASS.

## Round 4. Parser correctness

Four real defects surfaced here. The first two appeared in the first smoke run; the last two appeared in the demo output that was about to go into the README.

| ID | Evidence | Fix | Regression test |
|---|---|---|---|
| D1 | `LOG_LEVL` printed as `GHOST`. The typo join only paired ghosts with `MISSING` norms and allowed distance 2, which also made `DB_HOST` and `DB_PORT` a false pair. | Join against every consumed norm at distance 1. | `test_all_four_verdicts`, `test_no_false_typo_for_two_substitutions` |
| D2 | `config.yaml` produced `host` and `port` instead of `db.host` and `db.port`, so `DB_PORT` read by source looked missing. | Indentation stack for YAML containers, section prefix for TOML and INI. | `test_yaml_nested_keys_keep_parent_path`, `test_toml_section_prefix` |
| D3 | `app.json` emitted `feature` as a key alongside `feature.enabled`. A container is not a setting. | Emit leaf keys only from JSON flattening. | `test_json_flatten_produces_dotted_keys` |
| D4 | `cache.ttl` printed as `ttl`, because `cache` sat in the structural-word set and reset the YAML stack. | Apply structural-word filtering to GitHub Actions workflows only. | demo output check, `test_all_four_verdicts` |

After these fixes, six golden snapshots changed. That is expected during defect repair, so I re-froze them with `python3 scripts/make_golden.py` at the end of Round 7, before any refactor. The refactor was then required to match that frozen set with zero differences.

Verdict: PASS after fixes.

## Round 5. Output contracts

Focus: escaping, determinism, JSON and SARIF validity, no secret values, relative paths only.

Defect D5: `esc()` deleted ANSI CSI sequences from strings. On a file named `bad\x1b[31m.env`, the report showed `bad.env`, silently hiding hostile bytes and making two distinct filenames look identical. Fix: never delete. Escape control bytes, C1 controls and bidi overrides into visible `\xHH` or `\uHHHH` text. JSON already uses `ensure_ascii=True`.

Defect D6: a test asserted findings were sorted by normalized key alone. The documented contract sorts by verdict rank then key, so the test was wrong. Fixed the assertion to the contract. The program was correct here.

Evidence: `test_secret_value_never_in_report` seeds `sk_live_DO_NOT_LEAK_98765` and asserts it appears in none of the three formats. `test_deterministic_bytes_across_runs` compares SHA-256 across two runs of each format.

Verdict: PASS after fixes.

## Round 6. CLI and operational quality

Focus: help, version, unknown arguments, exit codes, stream separation, SIGPIPE, atomic writes, no writes without `--out`.

Defect D7: `python3 -m unittest discover -s tests` imports test modules as top-level names, so relative imports failed with `attempted relative import with no known parent package`. Fixed all test imports to absolute package imports. This was a harness defect, not a program defect.

Evidence: `--help` and `--version` write to stdout and exit 0 before any filesystem access. An unknown flag exits 2 with usage on stderr. An unresolvable root exits 2 with empty stdout. A mocked `BrokenPipeError` returns 1 with no traceback. `--out` writes through a temp file and `os.replace`, leaves no `.ghostkey-*` leftovers, and keeps stdout empty. `test_no_files_written_without_out` confirms no writes into the scanned tree.

Verdict: PASS after fixes.

## Round 7. Execution and supply-chain isolation

Focus: forbidden call sites, import allowlist, live network ban, no dynamic loading.

Evidence: `audit.py forbidden` walks the AST of every shipped module. A regex check would have produced a false positive on `re.compile`, so the gate looks at `ast.Import`, `ast.ImportFrom`, bare forbidden calls, and `os.system`/`os.popen` attributes. Zero hits. A live test patches `socket.socket` to raise and runs a full scan; the scan never touches it. Round 9 additionally checks that every imported root module is in `sys.stdlib_module_names`.

Verdict: PASS.

## Round 8. Architecture-refactor regression

Focus: deepen the codebase while changing zero observable behavior. This is the strictest round.

`scripts/deepen.py` reads v1 `core.py`, extracts every top-level node with `ast`, and writes each function body verbatim into one of seven modules. `core.py` becomes a facade re-exporting the frozen names. The interface `run(options)` and `main(argv)` does not move. The before-picture is saved at `docs/architecture/core_v1.py`.

Two defects surfaced during the refactor and both were caught by running the gates:

- Attempt 1 dropped `@dataclass` decorators, because `ast` reports a class line without its decorators. Symptom: `TypeError: Options() takes no arguments`. Fixed with a decorator-aware source extractor.
- Attempt 2 omitted `MAX_KEY_LEN` from `surfaces.py`. Symptom: `NameError: name 'MAX_KEY_LEN' is not defined`. Fixed the import list.

Restored v1, re-ran the splitter, and verified:

```text
=== gate: golden ===
[PASS] golden
Ran 44 tests in 4.295s
OK
```

Six frozen cases, byte-identical:

| Case | Bytes | SHA-256 prefix |
|---|---:|---|
| text | 1766 | `cd3a51221396` |
| json | 5664 | `85effb43369f` |
| sarif | 7646 | `45369bcd027d` |
| json_fail_none | 5664 | `85effb43369f` |
| json_exact | 6381 | `046186cb5791` |
| text_show_ok | 1804 | `7e450379c1c3` |

The mutation test changed `LOG_LEVL` to `LOG_LEVXL` in a copy of the fixture and confirmed the oracle reports a different hash. If the golden suite did not notice that change, it would not be observing behavior. `ARCHITECTURE-REVIEW.html` records the deepening with before and after diagrams and the two candidates deliberately not built.

Verdict: PASS. Zero functions changed.

## Round 9. Self-scan, imports and optimization

Focus: point the tool at its own repository, bound runtime, verify the stdlib-only claim, and check the packaged artifact.

Checks: scan `/data/workspace/ghostkey` with `--format json --fail-on none`, parse the result, assert exit 0, require completion under 5 seconds, and walk every shipped module's AST to confirm each imported root module is in `sys.stdlib_module_names`. Round 9 also verifies that the package gate finds every required file, that the pyproject version matches `core.VERSION`, and that the README states the current version with no placeholder text.

Verdict: PASS. `python3 scripts/audit.py all` reports `[PASS]` for every gate.

## What the rounds did not cover

Cross-platform behavior on Windows is untested here. The CI matrix covers Python 3.10, 3.11 and 3.12 on Linux. Windows path handling, reserved filenames and UTF-16 config files remain open. Full YAML 1.2, shell expansion and dynamically constructed keys are outside the parser's contract by design. Those limits are stated in `README.md` and `SECURITY.md`, not hidden.
