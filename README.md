# ghostkey

Config keys that silently do nothing. Found before they cost you a day.

You set `LOG_LEVL=debug` in `.env`. The code reads `LOG_LEVEL`. Nothing crashes. Nothing logs. The program uses its default and you spend an afternoon checking the network, the retry logic and the database before you look at the spelling of a key.

`ghostkey` reads key names across config files, Dockerfiles, CI workflows and source code. It joins them into one provenance record per key and reports three things: keys nobody reads, keys the code reads that nobody declares, and declared keys one character away from the key the code actually uses.

Current release: 1.0.0. Python 3.10 or newer. Standard library only. No network, no config file, no install required to try it.

## Run it

```sh
git clone <your-fork-url>
cd ghostkey
python3 -m ghostkey tests/fixtures/demo
```

Or install the command:

```sh
python3 -m pip install .
ghostkey .
```

The second command works in any repository. It does not care what language the project uses.

## What you see

Output excerpt from the bundled demo fixture:

```text
ghostkey 1.0.0  |  demo  |  9 files  |  17 keys

  KEY                          VERDICT  EVIDENCE
  ------------------------------------------------------------------------
  LOG_LEVL                     TYPO     .env.example:2
      Declared but never read. Matches a key the source does read: LOG_LEVEL.
      did you mean LOG_LEVEL (src/app.py:4)?
  API_BASE_URL                 MISSING  src/client.js:1
      Read by source, never declared or delivered.
  AWS_REGION                   MISSING  src/app.py:6
      Read by source, never declared or delivered.
  MODE                         MISSING  src/client.js:2
      Read by source, never declared or delivered.
  API_TOKEN                    GHOST    .env.example:4
      Declared or delivered, never read by source.
  ...
  db.host                      GHOST    config.yaml:2
      Declared or delivered, never read by source.

  1 typo  3 missing  10 ghost  3 ok  0 diagnostics
```

The `TYPO` line is the reason this tool exists. It joins a declared key to a consumed key across two files and names the exact source location.

## Options

```sh
ghostkey . --format json                 # ghostkey/1 schema, deterministic bytes
ghostkey . --format sarif                # SARIF 2.1.0 for code scanning
ghostkey . --out report.json             # atomic write, clean stdout
ghostkey . --fail-on typo                # gate CI on typo pairs only
ghostkey . --ignore LEGACY_KEY           # exclude a key, repeatable
ghostkey . --exact                       # stop folding case, dots and dashes
ghostkey . --show-ok                     # also list keys with supply and demand
ghostkey . --max-file-bytes 500000       # bound an untrusted tree
```

Exit codes: `0` clean, `1` findings, `2` bad arguments or scan error, `130` interrupted.

## What it reads

| Surface | Files | Role |
|---|---|---|
| Declaration | `.env*`, `.json`, `.toml`, `.ini`, `.cfg`, `.yaml`, `.yml` | supply |
| Delivery | `Dockerfile` `ENV`, GitHub Actions `env:` blocks | supply |
| Consumption | Python, JS/TS, Go, Ruby, Rust, Java source patterns | demand |
| Documentation | backticked uppercase keys in Markdown | evidence only |

Keys fold to one token: `db.host`, `DB_HOST` and `db-host` agree. Nested YAML and TOML sections keep their parent path, so `db.port` matches a source read of `DB_PORT`. `--exact` disables the folding.

## What it does not do

It never reads values. Parsers split on `=` or `:` and keep the left side. No secret value reaches a finding, a report, a diagnostic or a CI log.

It never executes repository code, never opens a socket, never writes into the scanned tree, and never edits a key. It cannot see dynamically constructed keys such as `os.getenv(prefix + "_TOKEN")`. It treats those as silence, not as proof. Static analysis has limits and this tool states them.

It does not replace a secret scanner, a schema validator or a documentation linter. It answers one question: for each key, which of the four roles are present, and which role is missing.

## Prior art

We did not invent config-key checking, and we do not claim to be first. `config-sentinel` covers JS/TS property access with a Node toolchain. `ConfigLedger` (v0.1) builds per-key provenance across code, CI and Docker for Python 3.12+. `dotenv-linter` checks `.env` format. `check-jsonschema` validates config against a supplied schema. `doc-drift` handles documentation-to-code drift for Python CLI flags and env vars.

`ghostkey` occupies a narrower gap: one offline command, no setup, cross-language consumption, cross-surface supply, typo attribution, and a report that never carries a value. See `DESIGN.md` for the rejected ideas and the evidence behind this boundary. If you find a mature tool that covers this exact job, open an issue and we will correct this section.

## Safety

The scanned tree is hostile input by default. Symlinks are never followed, containment is checked before every read, opened descriptors are re-checked with `fstat`, and file size, file count, depth, keys per file and findings are all bounded. Terminal output escapes control bytes instead of deleting them. `docs/adr/0001-safe-scanning.md` records the full decision. `SECURITY.md` explains how to report a problem.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 scripts/audit.py all
python3 scripts/make_golden.py     # only after an intentional behavior change
```

`REVIEW.md` logs eight review rounds with the commands and their output. `ARCHITECTURE-REVIEW.html` shows the before and after of the module deepening, with the frozen behavior contract that proves the refactor changed no function.

## License

MIT. See `LICENSE`.
