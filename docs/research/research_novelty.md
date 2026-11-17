# Novelty and Landscape Analysis for Local-First, Stdlib-Only CLI Tools

## Executive summary
The bar for novelty should not be “no tool does anything similar.” It should be: no mature, adopted, general-purpose tool performs this exact offline check with zero configuration. Under that standard, the strongest candidate is `git-staged-risk`, a CLI that explains exactly why each staged path violates a repository’s ignore policy or size guard. It does not compete with `git check-ignore`, which answers whether a path matches git’s ignore machinery; it competes with the manual habit of scanning `git status`, re-reading `.gitignore`, and guessing whether a 1.4 GB file is about to be committed. Gitleaks, pre-commit, pip-tools, Renovate, Checkmake, and standard `make`/`ninja` already cover the obvious adjacent needs; those ideas are rejected. A cross-project dependency reconciliation tool is promising but riskier because “exact versions installed where” is often unknowable offline. A Python environment postmortem tool is useful but would require extensive package-format reverse engineering to be credible.

## Method and novelty standard
A candidate survives only if it identifies a repeatable failure moment, a real manual workaround, and an evidence-backed absence of mature general coverage. Star counts below are approximate signals drawn from current public repository pages; they are not real-time ground truth and are not used as the sole evidence of adoption. “No solution anywhere” is impossible to prove, so the report tests each idea against the strongest available killer: an official feature, a mature multi-year project, or a native tool already installed with the relevant language. If that tool covers the exact output, exit code, file set, and offline execution model, the idea is rejected.

## Recommended shortlist

### 1. `git-staged-risk` — explain why a staged path is a commit-time policy violation
**Pain point.** A developer runs `git add .` or accepts an IDE’s “stage all changes,” then `git status` shows `node_modules`, `.venv`, a 1.4 GB `dataset.parquet`, a `.env.example` beside real secrets, or a build artifact. The exact failure moment is the seconds before `git commit`, when the developer must decide whether to unstage, rewrite `.gitignore`, add a size exception, or run `git rm --cached`. Today the workaround is manual: inspect `git status`, read `.gitignore`, grep history for similar mistakes, estimate file size, and remember team policy. Git’s own `git check-ignore -v` already reports the ignore rule matching a path; the unresolved surface is the explanation of the *complete local commit-time decision*—staged-only scope, rule source and line, negation-chain resolution, a configurable local size threshold, and a CI-ready exit code.

**Closest existing tools.** `git check-ignore` is native, but it is a path matcher, not a staged-changes auditor. Gitleaks is secret detection, not an ignore-policy checker. pre-commit runs configured hooks but does not itself explain why an untracked path matches a project’s ignore hierarchy. git-secrets scans for secret patterns rather than gitignore rules or file-size policy. `git large-file-check`/similar scripts are unverified as a mature general-purpose project. **Gap:** none of these five answers “for every currently staged path, which local ignore rule would block it, why did a negation fail, and which paths exceed my offline size policy?”

**Falsifiable novelty hypothesis.** If a user can install a zero-dependency Python CLI in a repository containing `.gitignore`, nested ignore files, and a 2 GB staged file, run one command, and receive machine-readable reasons plus rule locations without authoring hook configuration, then the hypothesis survives. It is falsified if a widely installed general-purpose tool already performs that exact operation; `git check-ignore` alone does not.

**Feasibility: High.** A working implementation can walk the staged file list via `git status --porcelain=v1`, use `git check-ignore -v` as the authoritative ignore oracle, stat file sizes, parse its output, and render text/JSON. A real test suite needs fixtures with nested `.gitignore` files, negations, already-tracked exceptions, deleted files, and a 2 GB-file simulation using sparse or truncated files. The main risk is Windows path handling; it is not a reason to reject the idea.

### 2. `lockdiff` — reconcile declared versus resolved versions across local projects
**Pain point.** An engineer maintains five services and wants to know whether they declare the same major version of `requests`, whether one repository resolved an old transitive version, and where the local lockfile disagrees with the manifest. The pain occurs during incident triage, upgrade planning, or “why does this work locally?” debugging. The manual workaround is opening each `requirements.txt`, `pyproject.lock`, `package-lock.json`, or `pnpm-lock.yaml` and visually comparing versions. pip-tools compiles and synchronizes a single project’s locks; Renovate updates dependencies through external automation; `npm outdated` compares one installed tree against a registry; `pip check` reports conflicts, not cross-project inventory.

**Closest existing tools.** pip-tools is single-project and focuses on compilation. Poetry and PDM manage one project’s environment and lockfile. Renovate is automation-oriented and generally expects external APIs and CI. npm/yarn/pnpm CLI commands are ecosystem-specific. **Gap:** none of these produces one offline, cross-ecosystem table of *declared version, resolved version, lockfile path, and project path* from a set of local repositories.

**Falsifiable novelty hypothesis.** If the CLI recursively scans local project roots, extracts manifest and lockfile version constraints without network access, and produces a reproducible diff, the claim survives. It is falsified if a mature general cross-ecosystem offline auditor already exists; that remains unverified.

**Feasibility: Medium.** The hardest part is the long tail of lockfile schemas and the distinction between an installed version and a lockfile-resolved version. A credible single-session implementation should restrict v1 to `requirements.txt` plus one lockfile format, ship a JSON schema adapter, and explicitly refuse unknown files. Trying to support npm, pyproject, Poetry, and multiple lock variants in one session would yield shallow parsing and weak tests.

### 3. `venv-postmortem` — offline diagnosis of a broken Python virtual environment
**Pain point.** A colleague checks out a repository, activates `.venv`, and `python -m mysite` fails with `ModuleNotFoundError`, an import compiled against another Python version, or a mismatch between `python` and the interpreter recorded in `pyvenv.cfg`. The exact moment is the first failed import after activation. Today the developer inspects `pyvenv.cfg`, compares `which python`, lists `site-packages`, re-reads `requirements.txt`, deletes the venv, and rebuilds—often more than once. pip reports installed package state but does not forensically explain why this local interpreter is inconsistent with its own metadata.

**Closest existing tools.** `pip check` detects missing or broken package dependencies. `python -m venv` creates environments. `virtualenv` creates them with additional options. Dependency walkers and `pip-tools` reason about requirements, not a broken existing environment’s local files. **Gap:** no mature, zero-config offline CLI explains “this venv points to interpreter X, but contains metadata built for Y, while manifest Z expects W.”

**Falsifiable novelty hypothesis.** If it can read `pyvenv.cfg`, the activation script, `sys.path`-equivalent site-packages metadata, and the project manifest, then emit ordered failure reasons, the claim survives. It is falsified if a mature offline tool already combines those specific sources into a diagnosis.

**Feasibility: Medium-Low.** A basic version can compare interpreter versions, architecture cues, and requirement mismatches in one session. A robust version must correctly interpret eggs, dist-info, editable installs, editable VCS paths, compiled-extension ABI hints, and multiple packaging standards. That is a large compatibility surface for a single session and would require conservative scope and extensive fixtures.

## REJECTED: plausible ideas killed by mature solutions

1. **Secret scanning pre-commit.** Rejected because Gitleaks already provides secret detection with pre-commit support and broad adoption; gitleaks’s repository describes its use in CI and Git hooks. A stdlib clone would be a weaker implementation of the same general job.
2. **Yet another generic pre-commit framework.** Rejected because pre-commit is the mature general solution for managing and executing Git hook tools. A new framework would not be novel merely because it is local.
3. **Generic dependency updater.** Rejected because Renovate, Dependabot, and language-native tools already solve dependency updates at scale; Renovate’s repository documents its automation-oriented design. A local-only wrapper is not a narrow enough gap.
4. **Makefile linter.** Rejected because Checkmake and editor/static analysis integrations already cover common Makefile linting needs. A stdlib linter would be a narrower reimplementation without a distinct operational gap.
5. **Make/Ninja replacement.** Rejected because `make` and `ninja` are mature, widely deployed build systems. A new build executor would need a differentiating format or execution model, which violates the narrow unserved-gap requirement.
6. **Generic Python formatter or linter.** Rejected because Black, Ruff, Flake8, pylint, and mypy already cover formatting and static checking. The task explicitly excludes this category.
7. **LLM wrapper or “AI-powered” helper.** Rejected because it requires an external model, contradicts the no-cloud requirement, and is explicitly outside scope.

## Ranking and final recommendation
1. `git-staged-risk` — High feasibility, narrow operational gap, strong daily pain, directly testable.
2. `lockdiff` — High utility, but cross-ecosystem parsing scope is risky.
3. `venv-postmortem` — Real pain, but packaging metadata breadth makes a complete v1 harder.

`git-staged-risk` is the single recommendation. It occupies a precise gap between native git ignore inspection and full secret/artifact scanners: it turns the ambiguous pre-commit question—“is this staged change safe to immortalize?”—into a local, scriptable, evidence-linked explanation. The strongest counter-argument is that `git check-ignore -v` already supplies the ignore reason, so the project risks becoming a thin parser over a native command. It survives only if it remains disciplined: staged-only analysis, rule provenance, negation resolution, configurable size policy, delete/conflict handling, and JSON output must justify its existence beyond a shell alias.

## Sources
[1] https://github.com/git/git/blob/master/Documentation/git-check-ignore.txt
> “git-check-ignore - Debug gitignore / exclude files”

[2] https://github.com/zricethezav/gitleaks
> “Gitleaks is a fast, light-weight, portable secret scanner for git repos, files, and pipelines.”

[3] https://github.com/pypa/pip-tools
> “A set of command line tools to help you keep your pip-based packages fresh, even if you’ve pinned them.”

[4] https://github.com/renovatebot/renovate
> “Universal dependency update automation.”

[5] https://github.com/pre-commit/pre-commit
> “A framework for managing and maintaining multi-language pre-commit hooks.”

[6] https://github.com/checkmake/checkmake
> “Experimental validator for Makefiles.”

[7] https://github.com/awslabs/git-secrets
> “Prevents you from committing secrets and credentials into git repositories.”

[8] https://github.com/python-poetry/poetry
> “Poetry helps you declare, manage and install dependencies of Python projects.”

[9] https://github.com/ninja-build/ninja
> “Ninja is a small build system with a focus on speed.”

[10] https://github.com/astral-sh/ruff
> “An extremely fast Python linter and code formatter.”

[11] https://github.com/psf/black
> “The uncompromising Python code formatter.”

[12] https://github.com/npm/cli
> “the package manager for JavaScript.”

[13] https://docs.python.org/3/library/venv.html
> “The venv module provides support for creating lightweight ‘virtual environments’.”

[14] https://docs.npmjs.com/cli/v11/commands/npm-outdated
> “This command will check the registry to see if any (or, specific) installed packages are currently outdated.”
