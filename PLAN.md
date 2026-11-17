# Workflow, agents and gates

The human partner is the sponsor. I am the lead and the only one who accepts work. Nothing ships because an agent said it was done; it ships because I ran the verification command and read the output.

## Skills fetched from GitHub and applied

21 `SKILL.md` files were pulled into the session from `anthropics/skills`, `mattpocock/skills`, `obra/superpowers`, `vercel-labs/agent-skills`, and `hardikpandya/stop-slop`. They are working discipline here, not installed runtime plugins. The relevant ones:

| Skill | How this project uses it |
|---|---|
| `superpowers/brainstorming` | Design doc written before code. Opted out of the interview gate on explicit instruction. |
| `mattpocock/grilling`, `grill-me` | The 12-question self-grilling log in `DESIGN.md`. |
| `superpowers/verification-before-completion` | No completion claim without a fresh command and its full output. |
| `superpowers/test-driven-development`, `mattpocock/tdd` | Red-green for parser and verdict behavior; golden snapshots before refactor. |
| `superpowers/systematic-debugging`, `mattpocock/diagnosing-bugs` | Reproduce, minimize, hypothesize, fix, regress. |
| `superpowers/requesting-code-review`, `mattpocock/code-review` | The 9 review rounds in `REVIEW.md`. |
| `mattpocock/improve-codebase-architecture`, `codebase-design` | Architecture pass with module/interface/depth/seam/adapter/leverage/locality vocabulary, HTML report, behavior freeze. |
| `hardikpandya/stop-slop` | README and docs: active voice, no filler, no em dashes, no quotables. |
| `vercel-labs/writing-guidelines` | Terse `file:line` style for review findings. |
| `anthropics/skill-creator` | `skills/ghostkey/SKILL.md` follows the portable SKILL.md format. |

All 21 `SKILL.md` files landed. Several `raw.githubusercontent.com` requests timed out, so a `cdn.jsdelivr.net` fallback and parallel retries completed the set. `superpowers/writing-plans` and `superpowers/code-review` arrived after the first batch timed out; I corrected the earlier "missing" note once I listed the directory. `docs/skills-installed.md` records the exact inventory and sizes.

## Agent roster

| Agent | Specialism | Deliverable | Acceptance test I applied |
|---|---|---|---|
| A1 | Novelty and landscape | `research_novelty.md` | **Rejected.** Its #1 pick was a thin `git check-ignore` wrapper. Sent back. |
| A1-r | Adversarial prior-art kill | `research_novelty_v2.md` | **Accepted.** Killed my `receipts` idea with named tools. Independently verified with a second search. |
| A2 | Star dynamics and distribution | `research_stars.md` | **Accepted.** Blunt, quantitative, no flattery. Base rate: 132 repos above 100k out of 32.6M starred repos. |
| A3 | Security and quality gates | `research_qa.md` | **Accepted with adaptation.** It assumed a secret scanner; I mapped its threat model onto a key-name scanner. 8 rounds and the golden strategy come from it. |
| Lead | Design, code, integration, all verification | This repository | Every gate below. |

A1's rejection and the independent re-verification of A1-r's evidence are the strictness checks. An agent that produces a weak recommendation goes back to work. An agent whose evidence I cannot reproduce does not get trusted.

## Workflow

```
Phase 0  Skill fetch + prior-art research            [done]
Phase 1  Self-grilling, design doc, novelty boundary [done]
Phase 2  Plan, agent roster, gate definitions        [done]
Phase 3  v1 implementation (single deep call path)  [build]
Phase 4  Tests: unit, safety, CLI, golden, property [build]
Phase 5  8 review rounds with fixes                 [verify]
Phase 6  Architecture deepening (behavior frozen)   [verify]
Phase 7  Round 8 regression + final evidence        [verify]
Phase 8  Package and deliver                       [verify]
```

## Gates

| Gate | Command | Pass criterion |
|---|---|---|
| G1 Syntax | `python3 -m compileall -q ghostkey` | exit 0 |
| G2 Unit + safety | `python3 -m unittest discover -s tests -v` | 0 failures, 0 errors |
| G3 Forbidden API | `python3 scripts/audit.py forbidden` | 0 hits |
| G4 Determinism | `python3 scripts/audit.py determinism` | identical sha256 across runs |
| G5 Golden | `python3 scripts/audit.py golden` | stdout/stderr/exit/bytes match frozen snapshots |
| G6 Rounds 1-7 | `python3 scripts/audit.py rounds` | every check passes, fixes logged in `REVIEW.md` |
| G7 Refactor freeze | `python3 scripts/audit.py golden` after refactor | byte-identical to pre-refactor snapshots |
| G8 Round 8 | `python3 scripts/audit.py regression` | frozen contract intact |
| G9 Packaging | `python3 scripts/audit.py package` | zip builds, README claims verified |

## The 9 review rounds

From `research_qa.md`, adapted to this tool, plus one final round so the examination exceeds eight. Each round has a focus, a check, and a pass/fail line in `REVIEW.md` with real command output.

1. Scope and threat model. Every input and output sink enumerated.
2. Filesystem and path safety. Symlinks, containment, special files, TOCTOU, permissions.
3. Resource limits. File size, file count, depth, keys per file, findings, decoding.
4. Parser correctness. Every surface adapter, false positives, no crafted pattern could hang.
5. Output contracts. Escaping, determinism, JSON/SARIF validity, no values in reports.
6. CLI and operational quality. Help, version, exit codes, streams, SIGPIPE, atomic writes.
7. Execution and supply-chain isolation. Forbidden calls, no network, no writes without `--out`.
8. Architecture-refactor regression. Golden, property and mutation suites byte-identical.
9. Self-scan, import allowlist, runtime bound and packaging check.

## Strictness rules

- An agent's report is evidence, not a result. I read the file and re-run its claims.
- A round that finds nothing still records the command and the output. No invented findings.
- A fix gets a regression test that fails before the fix. Red-green, not "looks right".
- The architecture pass adds zero features. Any output byte change fails G7.
- No claim of "done" until the last gate has been run in the same turn as the claim.
