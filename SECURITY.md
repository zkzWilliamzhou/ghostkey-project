# Security policy

## What counts as a security issue here

`ghostkey` reads repositories the user does not control. Report a problem if you can make it:

- read a file outside the supplied root, including through a symlink or a hardlink;
- hang, exhaust memory, or produce unbounded output on a crafted tree;
- execute repository code, import a module derived from repository content, or open a socket;
- place a secret value into stdout, stderr, a report or a diagnostic;
- write into the scanned tree without `--out`;
- emit raw control bytes that alter a terminal.

A wrong verdict, a false positive, or a missing language pattern is a bug, not a security issue. Open a normal issue for those.

## Supported versions

Only the latest released version receives fixes. This repository is at 1.0.0.

## How to report

Open an issue with a minimal fixture tree, the exact command, the observed output and the expected output. Do not paste real credentials into an issue. If the problem needs private disclosure, say so in the issue and a maintainer will provide a private channel.

## Design constraints a fix must keep

Fixes must preserve the rules in `docs/adr/0001-safe-scanning.md`: no execution, no network, no values, no writes into the scanned tree, bounded reads, deterministic output. A fix that changes observable output bytes needs a new report schema version and a migration test, not a silent tweak. Run `python3 scripts/audit.py all` before proposing a change.
