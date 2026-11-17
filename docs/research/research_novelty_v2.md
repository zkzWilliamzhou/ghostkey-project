# `receipts` should not be built as specified

## Recommendation: reject

The proposed `receipts` is not a new program. It is a curated CLI that combines seven narrow check categories—none of which is empty—but at least six of which are already covered by mature, established tools. The one non-obvious category, project-CLI flag drift, is itself being built publicly. The lead engineer’s brief requires a program whose function does not already exist and can truly make a difference. This candidate does not survive that test.

| Claim category | Mature incumbent(s) | Verdict |
|---|---|---|
| Backticked paths and local Markdown links | `remark-validate-links`, `markdown-link-check`, `lychee` | Covered; use existing tool |
| Fenced code examples execute correctly | Python `doctest`, Sphinx `sphinx.ext.doctest`, `pytest-codeblock`, `exdown`, `markdown-doctest`, `shelldoc`, `mdbook test`, rustdoc | Covered, often better |
| Docstring/API parameters match code | `docsig`, `pydoclint`, `darglint` | Covered |
| Minimum Python and dependency metadata | `check-jsonschema`, pip/PEP 621 validators, repository-specific checks | Mostly covered |
| Symbol or signature drift | `doc-drift`, Drift, `docdiff`, `interrogate` | Largely covered |

The `name=receipts` is occupied by an unrelated claim checker. That collision is a namespace risk, not the deciding issue. The deciding issue is that the proposed feature list reads as a menu of existing capabilities, not one defensible technical advance.

## Each named tool overlaps by design

`remark-validate-links` explicitly validates Markdown links and images against existing local files and headings in a Git repository; it does not check external URLs. `markdown-link-check` and `lychee` additionally check external URLs and are widely deployed in CI. `remark-validate-links`’s own documentation limits its offline checking to files and headings; the other two extend that scope to network URLs. For the first requested check—relative file paths and local links—these tools already provide the core function, often with more configuration, reporting formats, and production use than a new entrant would have on day one. [1][2][3]

`pytest-codeblock` collects Python code blocks from `.rst` and `.md`, can run them as pytest tests, supports fixtures, grouped blocks, skipping, and pyproject configuration, and outputs through pytest. `exdown` extracts Markdown code blocks for pytest to execute. `markdown-doctest` executes JavaScript examples from Markdown and was used by lodash, Moment, RxJS, xstream and related projects. `shelldoc` executes shell commands shown in Markdown and compares their output. `mdbook test` and rustdoc compile and run Rust documentation examples. Python `doctest` and `sphinx.ext.doctest` do the same for Python interactive examples and Sphinx documentation. [4][5][6][7][8][9][10][11]

These tools verify executable behavior rather than string resemblance. That is materially stronger than `receipts`’s proposed textual or AST comparison. A documented `--verbose` flag may appear in an `argparse` definition while producing the wrong behavior, while an example that omits an optional argument may still work. `receipts` would convert executable examples into a static pattern-recognition problem and lose information in the process.

`docsig` and `pydoclint` already check whether Python docstring parameters and documented return/raise behavior correspond to function signatures or implementations. `pydoclint` supports NumPy, Google, and Sphinx docstring styles, runs as a CLI or flake8 plugin, and provides pre-commit integration. `docsig` provides standalone, flake8, and pre-commit modes. Their narrow scope is an advantage: users can configure and trust a small checker whose errors are legible. `receipts` would obscure that boundary by mixing prose, metadata, signatures, and symbols in one tool. [12][13]

Vale, `write-good`, and `alex` lint prose style and inclusive language; they do not prove code claims. `doc8`, `actionlint`, and `check-jsonschema` lint documentation format, GitHub Actions, and JSON/YAML against schemas, respectively. `interrogate` measures docstring coverage. None is a complete “documentation verifier,” but that does not create a missing general category; it shows that the space is already decomposed into maintainable specializations. [14][15][16][17][18][19][20]

## Existing projects already occupy “docs versus code”

The name `receipts` is taken by an unrelated verifier. Its purpose is not relevant; the collision still creates documentation and distribution confusion. Searches for `claimcheck`, `docverify`, and `truthcheck` return projects with overlapping names but different targets, including Dafny proof-to-requirement comparison and AI-assisted README repair. Those projects do not establish prior art for the proposed Python checks, but they confirm that the obvious naming territory is crowded.

More importantly, `doc-drift` already implements the proposed core differently and more honestly. It uses Python AST to find documentation-promised environment variables and CLI flags, compares them with actual reads such as `os.environ`, `os.getenv`, and `argparse.add_argument`, and reports stale or undocumented names. It provides JSON output and non-zero exit codes. It explicitly limits itself to Python sources and argparse, calls out Click/Typer/docopt as unsupported, and requires an ignore mechanism for foreign commands such as `gh`. It does not claim to verify license text, Python-version metadata, or prose. [21]

Drift covers README and documentation code blocks across TypeScript/JavaScript, Python, Go, Rust, and Java, and checks renamed identifiers, parameter mismatches, return-type drift, removed functions, and stale signatures. `docdiff` detects stale documentation through explicit `@doc` annotations, Git history, and CI-oriented JSON/SARIF output. These tools do not together provide every check in the brief, but they remove the novelty premise that no documentation–code consistency verifier exists. [22][23]

## The exact gaps do not justify a new general tool

`receipts` could theoretically add five things that the sampled mature tools do not unify:

1. A single deterministic taxonomy with `CONFIRMED`, `BROKEN`, and `UNVERIFIABLE` results.
2. AST-based CLI flag comparison without executing the project’s binary.
3. License-text matching against a stated license.
4. Detection of network imports behind claims of “offline,” “air-gapped,” or “no network.”
5. Claims of “zero dependencies,” “stdlib only,” or “no third-party packages” checked against imports and declared dependencies.

The first is presentation, not new verification. The second is partially implemented by `doc-drift`, with the legitimate limitation that AST inspection cannot infer dynamic argument parsing. The last three are plausible new detectors, but each is a specialized lint rule rather than a product category.

A generic dependency detector would need to distinguish conditional imports, test-only dependencies, vendored code, namespace-package re-exports, optional features, and imports that are never reached. `requests`, for example, uses sockets; `urllib` also uses sockets. A checker would need a maintained list of network-inducing modules rather than guess from import names. That turns a simple static scan into an ongoing supply-chain classification project.

`UNVERIFIABLE` is necessary because natural-language claims such as “fast,” “secure,” or “easy to integrate” cannot be machine-checked. But the same escape hatch limits the tool’s value: its strongest claims must remain unverified, while users may treat the absence of a failure as broader assurance.

## If forced to build, narrow the program to one claim

The defensible novelty boundary is one sentence: **a repository-local, offline static verifier that proves claims of `stdlib`-only, zero-dependency, air-gapped, or no-network implementation by reconciling declared dependencies, Python imports, and a conservative network-API model, without executing the project or inventing semantics for uncheckable prose.**

That boundary excludes link checking, code execution, docstring parameter linting, license opinion, and general documentation drift—all of which already have better-established tools. It also excludes dynamically constructed `argparse` flags, which an AST-only tool cannot reliably verify.

The single most valuable claim type is **`stdlib`-only or zero-dependency**, because it appears in marketing-critical copy, can be checked against `pyproject.toml`/`setup.cfg`/`setup.py` and real `import` statements, and directly affects security, packaging, and audit outcomes. The other claims are weaker: “offline” may mean no telemetry, no required network at startup, no external dependencies, or merely optional connectivity; “air-gapped” is an environment property rather than a source-code property; and license matching is partly solved by existing license scanners.

## Three failure risks and concrete mitigations

**False positives.** Any dependency claim will misclassify vendored code, test dependencies, conditional imports, typing-only imports, or first-party submodules. Mitigation: parse `pyproject.toml`’s `[project.dependencies]` and `[project.optional-dependencies]` as authoritative, then classify imports into standard library, first-party, and third-party only when a package index mapping or explicit project allowlist is present. Produce `BROKEN` only for explicit contradiction, `UNVERIFIABLE` for ambiguous import graphs, and never infer a dependency claim from the absence of an import.

**Scope creep.** Once links, CLI flags, Python metadata, licenses, and symbols are added, the tool becomes a low-quality bundle of separate linters. Mitigation: ship exactly one detector and one machine-readable interface. Treat every additional claim type as a separate tool proposal with its own false-positive evaluation, corpus, and owner.

**Ecosystem breadth.** Standard library contents, conditional imports, and network-inducing APIs differ across Python versions and distributions. Mitigation: bind network-API rules to a declared `requires-python` and version-pinned standard-library definitions; refuse `BROKEN` when the running interpreter cannot resolve that version. Document unsupported package managers, namespace packages, C extensions, and runtime monkey-patching.

The evidence supports building one narrow detector or adopting `doc-drift`, `remark-validate-links`, `docsig`, and similar tools. It does not support a broad new “documentation claims” CLI.

## References

[1] https://unifiedjs.com/explore/package/remark-validate-links/
> “remark plugin to check that markdown links and images point to existing local files and headings in a Git repo.”

[2] https://github.com/tcort/markdown-link-check
> “markdown-link-check checks for broken links in Markdown files.”

[3] https://github.com/lycheeverse/lychee
> “lychee is a fast, async link checker.”

[4] https://pytest-codeblock.readthedocs.io/en/dev/quick_start_ref.html
> “pytest-codeblock collects Python code blocks from .rst and .md files and runs them as pytest tests.”

[5] https://github.com/HDembinski/exdown
> “Extract code blocks from Markdown… for testing code in your README files.”

[6] https://www.npmjs.com/package/markdown-doctest
> “markdown-doctest… will run all of the Javascript code examples tucked away in your markdown.”

[7] https://github.com/endocode/shelldoc
> “shelldoc tests Unix shell commands in Markdown files and reports the results.”

[8] https://github.com/rust-lang/mdBook
> “mdbook test: test Markdown files by running the Rust code examples through rustdoc.”

[9] https://doc.rust-lang.org/rustdoc/write-documentation/documentation-tests.html
> “rustdoc supports executing your documentation examples as tests.”

[10] https://docs.python.org/3/library/doctest.html
> “doctest… searches for pieces of text that look like interactive Python sessions.”

[11] https://www.sphinx-doc.org/en/master/usage/extensions/doctest.html
> “sphinx.ext.doctest… allows you to test snippets in your documentation.”

[12] https://pypi.org/project/docsig/
> “docsig is a Python documentation linter that ensures function and method signature parameters are properly documented in docstrings.”

[13] https://pypi.org/project/pydoclint/
> “A Python docstring linter… checks whether a docstring’s sections… match the function signature or function implementation.”

[14] https://vale.sh/
> “Vale brings code-like linting to prose.”

[15] https://github.com/btford/write-good
> “write-good is a naive linter for English prose.”

[16] https://github.com/get-alex/alex
> “alex — Catch insensitive, inconsiderate writing.”

[17] https://pypi.org/project/doc8/
> “doc8 is an opinionated style checker for rst… styles of documentation.”

[18] https://github.com/jsh9/pydoclint
> “pydoclint… can detect some quite a few style violations that darglint cannot.”

[19] https://github.com/rhysd/actionlint
> “actionlint is a linter for GitHub Actions workflow files.”

[20] https://check-jsonschema.readthedocs.io/en/stable/
> “check-jsonschema… validate JSON and YAML files using JSON Schema.”

[21] https://github.com/mgkvibez/doc-drift
> “docdrift reports the environment variables and CLI flags your documentation promises that the code no longer has.”

[22] https://marketplace.visualstudio.com/items?itemName=pallaprolus.drift
> “Drift… pairs documentation blocks… with their code anchors and flags potential staleness when the code changes.”

[23] https://github.com/StevenBock/docdiff
> “docdiff… detects when documentation becomes stale relative to code changes.”
