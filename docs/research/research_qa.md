# Security and Quality Gates for an Offline, Standard-Library-Only Repository Scanner

## Executive summary: the scanner must be a parser, not a runtime

This tool’s security boundary is the repository content: filenames, symlink targets, file types, byte contents, encodings, regex patterns, and report data are all hostile. The scanner must therefore open nothing by path string alone, execute nothing, import no third-party code, allocate only bounded buffers, and write nothing except through explicit output flags. Its safe design is a fixed state machine: `resolve canonical root` → `walk physical inodes` → `type-gate` → `bounded read` → `decode defensively` → `match precompiled patterns` → `escape evidence` → `sort deterministically` → `emit`. Any deviation is a defect.

The core paradox is that many convenient Python APIs implicitly cross a trust boundary. `Path('a/../b')` manipulation may collapse a segment that has a different meaning through a symlink; `os.stat` and `open` form a TOCTOU pair; `is_dir()` followed by `iterdir()` can be redirected; `read()` turns a hostile file into a memory attack; `re.search` turns attacker-controlled syntax into CPU consumption; and `print(path)` turns repository bytes into terminal control codes. Every such call must be replaced by a narrow primitive with an explicit invariant. OWASP explicitly treats untrusted downstream data as a validation and output-encoding problem [1], while CWE-150 warns that control sequences must be neutralized before terminal rendering [2].

The eight review rounds below turn these invariants into binary acceptance tests. The final round is not “feature complete”; it is a behavior contract: after any internal refactor, the same fixture must produce the same report bytes, exit code, ordered findings, stderr text, and file-system side effects. A refactor that changes even an error message has changed observable behavior and must fail.

## 1. A single canonical path and inode ledger prevents every filesystem-escape class

All path and scanning threats share one root cause: the tool reasons about a name that is not the object it later opens. The fix is never to “sanitize `..`” in strings. It is to resolve the root once, then retain both the canonical lexical path and the device/inode pair of every visited file.

| # | Threat | Concrete mitigation | Concrete passing test |
|---|---|---|---|
| F1 | Traversal / symlink escape | On startup, resolve the requested root with `Path.resolve(strict=True)` and require it to be a directory. During the walk, call `Path.resolve(strict=False)` after each directory entry; reject the entry if the resolved path is not `root.resolve().is_relative_to(root)` under a strict prefix check that also compares `os.path.commonpath`. | Create `root/target`, `root/escape -> ../outside`, and `root/loopdeep/a/b -> ../../../loopdeep`. Run the scanner with `--root root`. Assert that the resolved path of every emitted record starts with the canonical root and that `outside/secret` is never opened; assert failure if the supplied root itself escapes. |
| F2 | Symlink loop / duplicate work | Maintain a set of visited `(st_dev, st_ino)` tuples. Before opening a regular file or descending into a directory, call `os.stat()` on the resolved path and reject entries whose inode is already in the ledger; treat the command-line root itself as visited. | Create a directory symlink cycle six levels deep. Assert completion in bounded time, exactly one record per physical file, and a logged `symlink_loop` event whose path is inside the root. |
| F3 | Device, FIFO, socket | After resolving, call `os.stat()` and allow only `S_ISREG`. Reject `S_ISCHR`, `S_ISBLK`, `S_ISFIFO`, `S_ISSOCK`, and doors. Never call `os.stat` on the path used for opening; open the already-inspected regular file by its resolved `Path`. | Create `root/char` from `/dev/zero`, a FIFO, and a Unix socket. Assert zero bytes read, no open of a device, and a distinct skip record per non-regular type. |
| F4 | TOCTOU | Use one `os.stat` result to decide type and size, then `open` the resolved path within a narrow `try/except` block. Do not use `is_file()`/`is_dir()` and then `open()`. Retry is forbidden; a change is an error. | Use a fault-injection wrapper that swaps a regular file for a directory after `stat`. Assert the tool raises a deterministic `path_changed` error and does not read or descend. |

The key implementation rule is separation of identity and presentation. Internally, `dev/inode` proves loop freedom and physical uniqueness; externally, the resolved lexical path is used only as a display and reporting field. The report must never use the raw attacker-supplied name as an identity. This also limits information leakage: error output should contain the safe resolved path and a stable category, not raw bytes or OS error strings that may contain unprintable data.

## 2. Fixed-size readers and non-backtracking matchers bound resource consumption

Denial of service is the second failure mode. Repository size, file size, nesting depth, invalid encodings, and regex syntax must all be capped before parsing begins. Where a limit cannot be enforced, the input must be rejected rather than approximated.

| # | Threat | Concrete mitigation | Concrete passing test |
|---|---|---|---|
| R1 | Large file / memory exhaustion | Stream with `file.read(chunk_size)` where `chunk_size` is a constant such as 65,536 bytes. Refuse files whose `st_size > MAX_FILE_BYTES` before allocation. Match each chunk with `re.search` against a compiled pattern and retain only a bounded overlap buffer equal to the longest pattern minus one byte; discard tail bytes after they can no longer contribute to a match. | Create a 4 GiB sparse file containing no match, then a 4 GiB file with a match only in the last chunk. Assert resident memory stays under a fixed threshold and the match is reported. |
| R2 | Deep paths / nesting | Bound directory depth with a counter initialized at zero at the root; increment only on descent. Reject a directory when `depth > MAX_DEPTH`. Enforce a global wall-clock timeout and a maximum number of visited files. | Build a 100,000-deep directory chain. Assert termination within the time limit and an explicit `max_depth_exceeded` record. |
| R3 | Invalid UTF-8 / binary data | Read bytes only. Decode line fragments with `errors='replace'` into a reporting string, but never feed those replacement characters back into a regex. Keep raw bytes for matching and compute offsets by scanning the original byte stream. | Create files with `\x80`, overlong sequences, truncated multibyte sequences, and NUL bytes. Assert valid UTF-8 JSON output, correct byte offsets, and no decoder exception. |
| R4 | ReDoS / catastrophic backtracking | Keep regexes in a versioned rule file and reject overlapping quantifiers, nested quantifiers, and unanchored exponential groups in a rule linter. Compile once with `re.compile`, then fuzz each rule against long non-matching inputs and evil inputs for a fixed timeout per file. | Supply `(a+)+b`, `(a|a)+`, and a 100,000-character non-matching input. Assert the linter rejects the first two and the scanner processes the third within the timeout. |
| R5 | Quadratic algorithms | Sort findings after collection using `sorted(..., key=stable_key)`; use hash sets for rule suppression, direct iteration for chunked matching, and avoid regex across whole-file strings. Benchmark the largest accepted fixture and enforce a time-per-byte budget. | Create 200,000 files with one match each. Assert CPU time is linear within the accepted tolerance and output ordering is identical across runs. |
| R6 | Unbounded output | Apply `--max-findings` and `--max-bytes-per-finding`. After the cap, emit one terminal `output_truncated` record with the exact count of suppressed findings. | Produce 10 million trivial findings. Assert emitted report size stays below the cap and the truncation record is present. |

The chunked matcher is the subtle control here. A naive implementation reads the whole file and risks memory exhaustion; a line-based reader can miss a multi-line secret; a chunk-only reader can split a match across boundaries. The correct design keeps a small overlap region and proves, in a unit test, that a match spanning every possible boundary position is still detected.

## 3. Output must be data, not a command interpreter

Every finding field derived from the repository—path, line text, match evidence, rule message, and error detail—is untrusted data. The terminal is merely one renderer; JSON and SARIF are others. The tool must therefore encode data once at the output boundary and never interpolate repository content into executable syntax.

| # | Threat | Concrete mitigation | Concrete passing test |
|---|---|---|---|
| O1 | ANSI / control injection | In the terminal renderer, replace bytes `0x00–0x1F` and `0x7F` with `\xHH`, strip ANSI CSI/OSC sequences, and allow only a fixed set of safe whitespace and printable characters. Use `json.dump(..., ensure_ascii=True)` for JSON, which escapes non-ASCII and unprintable characters by default. Do not call `print()` directly on repository strings. | Include `\x1b]9;...`, `\r...\noverride:`, and bidirectional overrides in a file. Assert the terminal output contains only the escaped representation and the visible table is not corrupted. |
| O2 | Secret leakage | Never echo matched secrets. Redact with a constant placeholder, or reveal only a fixed prefix and entropy-free checksum. Add a secrets rule allowlist, mask all `--verbose` evidence, and test report strings with forbidden regexes. | Seed fixtures with AWS, GitHub, and private-key patterns. Assert the serialized report contains no full credential and that redaction length is stable. |
| O3 | Non-determinism | Sort files by their canonical relative path and findings by `(path, start_byte, rule_id)`. Do not iterate `os.listdir` order, `dict` insertion order, or thread scheduling order. Set `PYTHONHASHSEED=0` in tests. | Run the scanner 50 times over the same fixture tree. Assert `sha256` equality for JSON and SARIF bytes. |
| O4 | Windows paths/encoding | Normalize only for reporting with `pathlib.PurePosixPath` when emitting portable SARIF; preserve local display paths separately. Open files with an explicit `encoding` only where required and use UTF-8 for reports; test `\`, reserved names, long paths, MUTF-16LE config files, and CP1252 fixtures. | Scan a Windows-style fixture with `con.txt`, a trailing-space name, and a UTF-16LE file. Assert findings, canonical path, and exit code are correct. |

SARIF and JSON must be generated from the same immutable in-memory finding object. If terminal rendering, JSON, and SARIF each reformat the path or evidence independently, they will diverge. A single canonical serializer prevents that class of regression.

## 4. No execution boundary can be optional or best-effort

Accidental execution is not a configuration mistake; it is a forbidden call site. Likewise, errors must not become implicit side effects or privilege requirements.

| # | Threat | Mitigation | Test |
|---|---|---|---|
| E1 | Accidental execution | Forbid `eval`, `exec`, `compile`, `__import__`, `importlib`, `pickle`, `marshal`, `subprocess`, `os.system`, `os.popen`, `ctypes`, `shelve`, and dynamic `globals()`. Replace YAML parsing with a dedicated non-recursive parser that reads only the supported subset and rejects custom tags and duplicate keys. Static grep the source; CI fails on any addition. | Add a test file containing `!!python/object/apply:os.system ["id"]` and `eval("1+1")`. Assert the scanner only records the text and performs zero process, import, or network activity; assert the static allowlist rejects the commit. |
| E2 | Network / side effects | Import a fixed subset: `argparse`, `sys`, `os`, `re`, `json`, `io`, `stat`, `time`, `hashlib`, `fnmatch`, `pathlib`, `collections`, `enum`, `dataclasses`, `unittest.mock`. Run the suite under a proxy that fails any socket. Writes are allowed only when the user passes `--out`; otherwise write only to `sys.stdout`/`sys.stderr`. | Monkeypatch `socket.socket` to raise. Assert all unit, fuzz, and golden tests pass with no network calls. Run with no flags and assert no files are created. |
| E3 | Permission errors | Walk continues on `PermissionError`, `FileNotFoundError`, and `NotADirectoryError`; each becomes one finding of severity `error` with the stable category. The scanner returns exit code `2` only after all accessible inputs are processed. | Remove read and execute bits from a subdirectory. Assert the scan finishes, the error path is escaped, and the exit code is `2`. |

The boundary must be enforced in three places: the import list, the static scanner, and the behavior test. A test that only checks for `subprocess` will miss `ctypes`, `importlib`, or a future contributor adding a plugin loader. Conversely, a static check with no live network test can miss an indirect import hidden behind an innocuous standard-library call.

## 5. CLI quality is part of the security boundary

A CLI is exploitable when its argument parsing, output streams, termination, and help behavior are inconsistent. Standard streams must carry distinct information: `stdout` is the report, `stderr` is operational status, and a broken consumer must never cause partial writes to be mistaken for success.

| Check | Required behavior |
|---|---|
| Argument parsing | `argparse` must reject unknown arguments with usage on `stderr` and exit code `2` [3]. Required positional `ROOT`, `--format {json,sarif,text}`, `--out`, `--max-file-bytes`, `--max-depth`, `--max-findings`, `--sort`, and `--seed` must be explicitly typed. |
| Help and version | `--help` prints to `stdout` and exits `0`; `--version` prints `name version` and exits `0`. No filesystem access occurs for either flag. |
| Exit codes | `0` = clean scan, no findings; `1` = findings reported; `2` = invalid arguments or scan errors; `130` = SIGINT. No other codes are allowed. |
| Stream separation | Reports go to `stdout`; scan warnings, progress, and internal errors go to `stderr`. Redirection must not alter exit semantics. |
| Encoding | Reports are UTF-8 with `\n`. `sys.stdout` errors must not crash during escape encoding; invalid characters are replaced or escaped at the renderer. |
| SIGPIPE | Catch `BrokenPipeError` around the output loop, drain remaining writes to `os.devnull`, and exit `1`; do not reset SIGPIPE to `SIG_DFL` [4]. |
| Reproducibility | `--seed` fixes any random sampling; sorting and output bytes are otherwise deterministic. |
| Side effects | No files are written unless `--out` is supplied; existing report files are replaced only after the report is fully serialized to a temporary file and atomically renamed. |

The most important CLI property is that `--help` and `--version` must run before any repository access. Otherwise, a malformed hostile repository could influence usage output, and a user investigating the tool could inadvertently trigger filesystem activity.

## 6. The eight review rounds form a gate, not a checklist

| Round | Focus | Checks | Pass/fail criterion |
|---|---|---|---|
| 1 — Scope and threat model | Confirm the security boundary | Every input source and output sink is enumerated; threat-to-control traceability exists; no untrusted input is trusted. | Every threat in this report maps to at least one test; no uncovered repository input remains. |
| 2 — Filesystem and path safety | Path handling, symlinks, special files | Resolve root; `is_relative_to`; inode ledger; `S_ISREG`; TOCTOU rejection; permission/access errors. | All fixture tests pass; no escape, loop, device open, or double-open occurs under fault injection. |
| 3 — Resource limits and parsing | DoS resistance | File/memory cap; streaming; overlap matcher; depth/file/time caps; encoding handling; output cap. | Scanner completes within budget on every large and malformed fixture; no memory growth beyond cap. |
| 4 — Regex and matching correctness | Rules cannot execute or hang | Rule linter, static pattern restrictions, compiled cache, per-file timeout, byte offsets, secret redaction. | Every rule passes fuzz/death tests; no catastrophic match exceeds budget; false negatives are demonstrated on boundary cases. |
| 5 — Output and report contracts | Reports cannot carry hostile rendering | JSON/SARIF/terminal encoding; control replacement; path normalization; deterministic ordering; truncation. | Canonical fixtures produce identical hashes; malicious control bytes cannot alter terminal or report structure. |
| 6 — CLI, I/O, and operational quality | The command surface is safe and predictable | `argparse`; exit codes; `--help`/`--version`; `stdout`/`stderr`; SIGPIPE; encoding; atomic writes; network ban. | All CLI scenarios and stream/proxy tests pass; no writes occur without `--out`. |
| 7 — Execution and supply-chain isolation | The tool cannot become a runtime | Forbidden-API scan, import allowlist, pickle/yaml/subprocess bans, mocked execution tests, plugin/extension ban. | Zero forbidden calls in source and zero executions or network calls in behavioral tests. |
| 8 — Architecture-refactor regression | Refactors preserve behavior | Every internal module may change only behind a frozen `ScanResult` contract; no public output changes without a versioned schema change. | Golden suite, diff suite, fuzz suite, and property tests all pass with byte-identical output where required. |

Round 8 is intentionally the strictest. Internal improvements are valuable only if they do not alter the security interpretation of existing reports. New matcher engines, parallel dispatchers, caching layers, and path-resolution strategies must all be treated as untrusted implementations of a stable contract.

## 7. A three-layer golden suite proves a refactor changed nothing

Behavior preservation requires a fixed input contract, a fixed output oracle, and an exact comparison. The suite must cover the cases users rely on—findings, severity, location, and report format—not merely internal method calls.

The **golden layer** contains cryptographically stable fixtures: minimal repositories, adversarial names and contents, and approved report snapshots. A test invokes the real `main(argv)` capture, capturing `stdout`, `stderr`, exit code, and created files. It compares the result with `expected.json`, which records:

```json
{
  "argv": ["scan", "fixture/root", "--format", "sarif"],
  "exit_code": 1,
  "stdout_sha256": "fixed hash of canonical report",
  "stderr_exact": "fixed normalized diagnostic text",
  "files_created": [],
  "files_modified": [],
  "findings": [
    {
      "rule_id": "fixed",
      "path": "subdir/evil.txt",
      "start_byte": 42,
      "severity": "high"
    }
  ]
}
```

A diff-aware comparator first normalizes line endings only where the format permits, then compares byte-for-byte. It treats different ordering, an extra trailing space, a changed ANSI escape, or a modified error message as a failure. Tests must run on Linux, macOS, and Windows runners because path representation can otherwise hide platform-specific behavior changes.

The **property layer** supplies generated hostile trees: random names with every problematic byte, random symlink graphs, duplicate inodes, mixed encodings, and random matches split across chunk boundaries. It asserts invariants such as:

- every emitted path is under the resolved root;
- every byte offset is within the reported file;
- findings are sorted;
- memory stays under its cap;
- scan duration stays under its cap;
- no external process, import, or network socket is created.

The **mutation layer** confirms the suite detects real changes. Deliberately alter a severity, byte offset, sort key, redaction rule, or terminal escape and run the suite. If the golden tests do not fail, they are not observing behavior—they are merely exercising code.

The architecture must encode this separation. A `Scanner` returns an immutable `ScanResult` containing `findings`, `errors`, `skipped`, and a monotonic event log. Renderers consume that result but cannot change it. Refactors may optimize `Scanner._walk`, replace `re` with a DFA, parallelize I/O, or restructure internal caching, but only if they return a `ScanResult` whose canonical serialization is identical. If a behavior change is genuinely required, it must be a new major report version with an explicit migration test—not a silent output tweak.

This contract is stricter than ordinary regression testing because it protects security consumers. A changed severity, truncated evidence field, or reordered SARIF result may alter an automated review decision. The golden suite therefore treats those changes as contract violations until they are deliberately versioned and reviewed.

## References

[1] https://owasp.org/Top10/2021/zh-Hant/A00_2021_Introduction/
> “A04:2021-不安全设计……如果我们真的希望让整个产业‘向左移动’，那我们必须进一步的往威胁建模，安全设计模块的观念，和安全参考架构前进。”

[2] https://cwe.mitre.org/data/definitions/150.html
> “The product receives input from an upstream component, but it does not neutralize or incorrectly neutralizes special elements that could be interpreted as escape, meta, or control character sequences.”

[3] https://docs.python.org/3/library/argparse.html
> “Normally, when you pass an invalid argument list to the parse_args() method… it will print a message to sys.stderr and exit with a status code of 2.”

[4] https://docs.python.org/3/library/signal.html
> “Piping output of your program to tools like head(1) will cause a SIGPIPE signal… This results in an exception like BrokenPipeError.”

[5] https://docs.python.org/3/library/subprocess.html
> “This library will not implicitly choose to call a system shell… all characters, including shell metacharacters, can safely be passed to child processes.”

[6] https://docs.python.org/3/library/pathlib.html
> “Pure paths… simply don’t have any OS-accessing operations.”

[7] https://docs.python.org/3/library/json.html
> “If True (default), the JSON output is guaranteed to have all incoming non-ASCII characters escaped.”

[8] https://docs.python.org/3/library/sys.html
> “Under some conditions stdin, stdout and stderr… can be None. It is usually the case for Windows GUI apps… started with pythonw.”