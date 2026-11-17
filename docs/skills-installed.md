# Skills fetched from GitHub

21 `SKILL.md` files were downloaded into the session at `/data/workspace/.skills/<name>/SKILL.md`. They are working discipline for this build, not runtime plugins. GitHub `raw` worked for some requests and timed out for others, so a `cdn.jsdelivr.net` fallback and parallel retries completed the set. Third-party files keep their own licenses; this repository redistributes none of them. `skills/ghostkey/SKILL.md` is the one skill authored here, in the portable Agent Skills format.

| Local name | Upstream | Bytes |
|---|---|---:|
| anthropics-skill-creator | anthropics/skills | 33168 |
| anthropics-template | anthropics/skills | 140 |
| mattpocock-code-review | mattpocock/skills | 6721 |
| mattpocock-codebase-design | mattpocock/skills | 6446 |
| mattpocock-diagnosing-bugs | mattpocock/skills | 8664 |
| mattpocock-domain-modeling | mattpocock/skills | 3346 |
| mattpocock-grill-me | mattpocock/skills | 157 |
| mattpocock-grill-with-docs | mattpocock/skills | 247 |
| mattpocock-grilling | mattpocock/skills | 2077 |
| mattpocock-improve-codebase-architecture | mattpocock/skills | 6028 |
| mattpocock-tdd | mattpocock/skills | 3629 |
| stop-slop-hardikpandya | hardikpandya/stop-slop | 2629 |
| superpowers-brainstorming | obra/superpowers | 15190 |
| superpowers-code-review | obra/superpowers | 2974 |
| superpowers-parallel-agents | obra/superpowers | 6078 |
| superpowers-subagent-dev | obra/superpowers | 19740 |
| superpowers-systematic-debugging | obra/superpowers | 9530 |
| superpowers-tdd | obra/superpowers | 9578 |
| superpowers-verification | obra/superpowers | 3646 |
| superpowers-writing-plans | obra/superpowers | 10335 |
| vercel-writing-guidelines | vercel-labs/agent-skills | 1233 |

Two dishes from this table were thin stubs that delegate to another skill: `grill-me` points to `grilling`, and `grill-with-docs` is a short wrapper. I read the full `grilling` and `brainstorming` files instead of treating the stubs as complete.

## What was applied

| Method | Where it shows up |
|---|---|
| Socratic design questions and a written design before code | `DESIGN.md` self-grilling log, 12 questions |
| Red-green TDD and regression tests | `tests/`, `REVIEW.md` defects D1 to D8 |
| Evidence before any completion claim | `scripts/audit.py`, nine rounds with command output |
| Systematic debugging | `REVIEW.md` defect table: symptom, cause, fix, test |
| Deep modules, interface, depth, seam, adapter, leverage, locality | `ARCHITECTURE-REVIEW.html`, `GLOSSARY.md`, `scripts/deepen.py` |
| No AI writing patterns | README and docs: active voice, no filler, no em dashes, no quotables |
| Portable SKILL.md format | `skills/ghostkey/SKILL.md` |

The brainstorming skill requires human approval of a design doc before implementation. The sponsor explicitly opted out of questions and said to work until done, so that gate was waived and the decision is recorded at the top of `DESIGN.md`.

Research outputs from the specialist agents live in `docs/research/`. Agent A1's first report was rejected and reworked; the rejection and the independent verification of its evidence are recorded in `PLAN.md`.
