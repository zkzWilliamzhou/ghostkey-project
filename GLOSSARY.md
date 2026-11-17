# GLOSSARY.md

Shared domain language. Used in code, docs and review findings. Adding a concept to the code means adding a term here first.

| Term | Meaning |
|---|---|
| **Key** | The name of a setting, never its value. `DATABASE_URL` and `db.host` are keys. Values are discarded at the parser boundary. |
| **Surface** | One place a key can appear. Four kinds: declaration, delivery, consumption, documentation. |
| **Declaration** | A key written in a config file: `.env*`, `.json`, `.toml`, `.ini`, `.cfg`, `.yaml`, `.yml`. |
| **Delivery** | A key supplied to the process by infrastructure: `Dockerfile` `ENV`/`ARG`, GitHub Actions `env:` blocks. |
| **Consumption** | A key read by source code: `os.getenv`, `process.env`, `os.Getenv`, `ENV[]`, `env::var`, `System.getenv`. |
| **Documentation** | A backticked uppercase key mentioned in Markdown. It never drives a verdict by itself. |
| **Evidence** | One observed occurrence: surface, relative file, line number, raw key. |
| **Normalized key** | The join token. Split camelCase, uppercase, fold non-alphanumeric runs to `_`, trim. `db.host` and `DB_HOST` agree. |
| **Supply** | Declaration plus delivery evidence for a normalized key. |
| **Demand** | Consumption evidence for a normalized key. |
| **Ghost** | Supply with no demand. A key someone set that no code reads. |
| **Missing** | Demand with no supply. Code reads a key nobody declared. |
| **Typo pair** | A ghost whose normalized key is within edit distance 2 of a normalized key that has demand. The report names the consumed key and its evidence location. |
| **Ambient key** | An OS or CI variable that appears in config but is not application configuration: `PATH`, `HOME`, `LANG`, `CI`. Excluded by default. |
| **Diagnostic** | A skipped file or a bounded condition, reported with a stable code. It is not a verdict about a key. |
| **Finding** | A ghost, missing, or typo pair with its evidence list. |
| **Report** | The immutable result of one scan: findings, counts, diagnostics, limits, schema version. |
| **Module** | Anything with an interface and an implementation. |
| **Interface** | Everything a caller must know to use a module correctly, including invariants and error modes. |
| **Depth** | Leverage at the interface: how much behaviour a caller gets per unit of interface learned. |
| **Seam** | The place where an interface lives and behaviour can be swapped. |
| **Adapter** | A concrete thing that satisfies an interface at a seam. |
| **Leverage** | What callers get from depth. |
| **Locality** | What maintainers get from depth: change concentrates in one place. |
