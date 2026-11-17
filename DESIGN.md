# Design: ghostkey

Status: approved by the lead. The human partner opted out of interview questions ("start working until the work is done"), so the brainstorming gate is waived. Written before implementation, as the design record.

## The constraint I cannot honestly satisfy

The brief asks for a function that does not exist anywhere in the world. I cannot prove that, and I will not pretend to. In 2026 every obvious developer-tool category has some prior art. The defensible standard I used instead: **no mature, widely adopted, general-purpose tool solves this exact job offline with zero configuration.** I list the prior art below and in the README. If a reader finds a mature incumbent that covers ghostkey's exact function, the novelty claim is wrong and should be corrected.

## Self-grilling log

I ran the grilling method against myself. Each question had to change what gets built or it was discarded.

**Q1. What is the most expensive class of silent bug you have actually watched a developer lose a day to?**
A setting that was written down and never read. `TIMEOUT_MS=5000` in `.env`, while the code reads `TIMEOUT`. Nothing crashes. Nothing logs. The program just uses the default. The developer debugging it checks the network, the database, the retry logic, and never thinks to check the spelling of a key. That is the pain. It is frequent, it is language-independent, and it has a one-line demonstration.

**Q2. Why has nobody fixed it?**
Linters work on one file. A config key lives in one file, gets delivered by another (CI, Docker, compose), gets consumed in a third (source), and gets documented in a fourth. Format-specific linters see one surface. Secret scanners see values, not names. Static analyzers see one language. The bug lives in the gap between surfaces.

**Q3. Is this just a link checker for config keys?**
No. A link checker asks "does this target exist?". ghostkey asks "for this key, which of four roles are present, and which role is missing?". The output is a provenance record per key, not a list of broken links.

**Q4. What makes it more than a linter rule?**
The typo attribution. A ghost key with edit distance <= 2 from a key that the code actually reads is not noise, it is the bug. `LOG_LEVL` declared, `LOG_LEVEL` consumed, one report line joining them: "did you mean LOG_LEVEL (src/app.py:44)?". That requires the cross-surface join. No single-file linter can produce it.

**Q5. What did I reject, and why?**
- `git-staged-risk`: a specialist agent recommended it. I rejected it. By its own admission it is a thin wrapper over `git check-ignore -v`. It also requires git to be installed, which breaks the offline/zero-config promise.
- `lockdiff`, `venv-postmortem`: narrow maintenance helpers, weak daily frequency, large compatibility surface.
- `receipts` (documentation claim verifier): I liked this one. A second specialist agent killed it with evidence, and I verified the kill independently. `remark-validate-links`, `lychee`, `markdown-link-check`, Python `doctest`, Sphinx doctest, `pytest-codeblock`, `exdown`, `shelldoc`, `mdbook test`, `docsig`, `pydoclint`, and `doc-drift` already cover its checks. Building it would have produced a low-quality bundle of existing linters. Rejected.
- `contract-diff` (user-visible change detector across two trees): powerful, but `cargo-semver-checks`, `revapi`, `oasdiff`, and `buf breaking` occupy adjacent territory, and a language-agnostic version cannot be built well in one session. Rejected on feasibility.

**Q6. What is the prior art for the surviving idea?**
- `config-sentinel` (npm): JS/TS only, requires a config file and a Node toolchain, one maintainer. It finds missing and unused keys from AST property access.
- `ConfigLedger` (v0.1, 1 star at time of research): cross-surface provenance across code, CI, Docker and docs, Python 3.12+, pip install, cache and baseline commands. Early stage, not mature.
- `dotenv-linter`: checks `.env` file format and duplicates, not cross-surface consumption.
- `check-jsonschema`: validates config against a supplied schema. Requires a schema.
None of these is an offline, zero-config, cross-language, cross-surface key provenance tool with typo attribution. I say "none that I found", not "none exists".

**Q7. What is the strongest argument against building this?**
Static analysis cannot see dynamically constructed keys. `os.getenv(prefix + "_TOKEN")` is invisible, so a correct key may be reported as a ghost. That is a false positive, and false positives kill linters. Mitigation: ghostkey never edits files, never claims certainty, caps what it reports, ships an ambient-key allowlist and `--ignore`, and labels every finding with the exact evidence files and lines so a human can dismiss it in two seconds. A finding you can disprove instantly is cheaper than a bug you cannot find at all.

**Q8. What would make this a failure even if it works technically?**
Collecting secret values. A config scanner that prints `STRIPE_KEY=sk_live_...` into CI logs is worse than the bug it fixes. Hard rule: ghostkey parses key names only and discards values at the parser boundary. No value ever reaches a finding, a report, or a diagnostic. This is an anti-goal with a test.

**Q9. Why Python, stdlib only, single file to start?**
A tool that audits other people's repositories must not require a toolchain, a package index, or a network connection. `python3 ghostkey.py .` has to work on a clean machine. No dependencies also means no supply chain to trust. Starting as one module gives us a clean before-picture for the architecture pass.

**Q10. What does "powerful" mean here?**
One command, any language, any repo, no setup, output that a CI gate and a human can both read: text, JSON, SARIF. Deterministic bytes. Stable exit codes. Bounded resources on hostile input.

**Q11. How do we prove the architecture refactor changed nothing?**
Golden snapshots captured from v1 before the refactor: stdout, stderr, exit code, and file side effects for fixed fixtures. After the refactor, byte-for-byte comparison. A mutation test proves the oracle actually detects a changed verdict. No new features in the refactor. Round 8 of the review gate fails if any byte differs.

**Q12. What is deliberately out of scope?**
Auto-fixing keys, reading values, YAML 1.2 full grammar, shell variable expansion, dynamic key construction, monorepo-specific policy, network calls, plugins, telemetry, and any write to the scanned repository.

## Approaches considered

1. **Config-file-only linter.** Parse `.env` and YAML, flag unknown keys against a schema. Rejected: needs a schema the repo does not have, and cannot see consumption.
2. **Runtime tracing.** Instrument the application, record which keys it reads at runtime, diff against config. Rejected: requires executing untrusted code, breaks offline/local-first, and only sees the paths the test run exercised.
3. **Static cross-surface provenance (chosen).** Parse declaration, delivery, consumption, and documentation surfaces without executing anything, join on a normalized key, and report the missing role. Chosen because it is offline, safe on hostile repos, language-agnostic, and makes the typo join possible.

## Goals, non-goals, anti-goals

Goals: find ghost keys, missing keys and typo pairs; run on any repo with one command; never leak values; be deterministic and resource-bounded; produce CI-consumable output.

Non-goals: fixing files, full-fidelity parsing of every config grammar, runtime verification, plugin ecosystem, performance records.

Anti-goals: printing secret values, executing repository code, touching the network, writing into the scanned tree, inventing verdicts when evidence is ambiguous, growing into a general documentation linter.

## Design

**Surfaces.** `declaration` (`.env*`, `.json`, `.toml`, `.ini/.cfg`, `.yaml/.yml`), `delivery` (`Dockerfile` ENV/ARG, GitHub Actions `env:` blocks), `consumption` (Python `os.getenv`/`os.environ`, JS/TS `process.env`/`import.meta.env`/`Deno.env.get`, Go `os.Getenv`/`os.LookupEnv`, Ruby `ENV[]`/`ENV.fetch`, Rust `env::var`, Java `System.getenv`), `documentation` (backticked uppercase keys in Markdown).

**Join.** Every key becomes a normalized token: split camelCase, uppercase, fold every non-alphanumeric run to `_`, trim. `db.host`, `DB_HOST`, and `db-host` agree. `--exact` disables folding. Keys under 3 characters, ambient OS variables, and `--ignore` entries are excluded.

**Verdicts.** `OK` (supply and demand), `GHOST` (supply, no demand), `MISSING` (demand, no supply), `TYPO` (a ghost within edit distance 2 of a consumed key, with the suggestion). Documentation-only keys are dropped from findings; prose is not configuration.

**Trust boundary.** The scanned tree is hostile. Resolve the root once, never follow symlinks, gate on `S_ISREG`, verify containment with `commonpath`, track `(st_dev, st_ino)` to stop loops, re-check the opened descriptor with `fstat`, cap file size, file count, depth, keys per file and findings, decode with replacement, escape control characters in text output, and never call eval, exec, subprocess, socket, pickle, importlib or a YAML loader.

**Output.** `text` (terminal table with escaped fields), `json` (schema `ghostkey/1`, sorted, `ensure_ascii=True`), `sarif` (SARIF 2.1.0 subset). No timestamps, no absolute paths, no nondeterministic ordering. Exit codes: 0 clean, 1 failing findings, 2 invalid arguments or scan error, 130 SIGINT.

**What is left to the builder.** Exact parser conservatism, the ambient allowlist, and the wording of each diagnostic. They are implementation calls, recorded in `GLOSSARY.md` and `docs/adr/`.
