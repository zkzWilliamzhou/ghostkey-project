"""ghostkey core, version 1.

Deliberately flat: walker, surface parsers, analysis and renderers live in one
module. This is the before-picture for the architecture deepening recorded in
ARCHITECTURE-REVIEW.html. The public interface is run(options) -> ScanResult.
"""
from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

VERSION = "1.0.0"
SCHEMA = "ghostkey/1"

DEFAULT_MAX_FILE_BYTES = 1_000_000
DEFAULT_MAX_FILES = 20_000
DEFAULT_MAX_DEPTH = 32
DEFAULT_MAX_FINDINGS = 5_000
MAX_KEYS_PER_FILE = 2_000
MAX_KEY_LEN = 128
MAX_EVIDENCE_PER_FINDING = 8
MAX_JSON_DEPTH = 8

EXCLUDED_DIRS = frozenset(
    {
        ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
        ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
        "target", ".idea", ".vscode", "site-packages",
    }
)

AMBIENT_KEYS = frozenset(
    {
        "PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TERM", "SHELL",
        "USER", "PWD", "TMPDIR", "HOSTNAME", "CI", "GITHUB_ACTIONS",
        "GITHUB_WORKSPACE", "RUNNER_OS", "RUNNER_ARCH", "DEBIAN_FRONTEND",
        "PYTHONPATH", "PYTHONHASHSEED", "NODE_OPTIONS", "GOPATH", "CARGO_HOME",
    }
)

STRUCTURAL_WORDS = frozenset(
    {
        "env", "environment", "vars", "secrets", "services", "jobs", "steps",
        "with", "defaults", "config", "settings", "options", "variables",
        "matrix", "strategy", "include", "extends", "on", "name", "uses",
        "run", "image", "ports", "volumes", "depends_on", "build", "context",
        "dockerfile", "deploy", "stages", "stage", "script", "cache",
        "artifacts", "needs", "runs_on", "working_directory", "shell", "when",
        "key", "value", "id", "if", "inputs", "outputs", "description",
        "runs-on", "working-directory", "timeout-minutes", "continue-on-error",
    }
)

SECTION_HEADER = re.compile(r"^\s*\[([^\]]+)\]\s*$")

KEY_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")
CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
NON_ALNUM = re.compile(r"[^A-Z0-9]+")
DOC_KEY = re.compile(r"`([A-Z][A-Z0-9_]{2,})`")
YAML_KEY = re.compile(r"^\s*(?:-\s*)?([A-Za-z_][A-Za-z0-9_.\-]*)\s*[:=]\s*(.*)$")
DOCKER_ENV = re.compile(r"^ENV\s+(.+)$", re.IGNORECASE)

CONSUMPTION_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"""\bgetenv\s*\(\s*["']([A-Za-z_][A-Za-z0-9_.\-]*)["']""",
        r"""\benviron\.get\s*\(\s*["']([A-Za-z_][A-Za-z0-9_.\-]*)["']""",
        r"""\benviron\s*\[\s*["']([A-Za-z_][A-Za-z0-9_.\-]*)["']\s*\]""",
        r"""\bprocess\.env\s*\[\s*["']([A-Za-z_][A-Za-z0-9_.\-]*)["']\s*\]""",
        r"""\bprocess\.env\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)""",
        r"""\bimport\.meta\.env\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)""",
        r"""\bDeno\.env\.get\s*\(\s*["']([A-Za-z_][A-Za-z0-9_.\-]*)["']""",
        r"""\bos\.(?:Getenv|LookupEnv)\s*\(\s*["']([A-Za-z_][A-Za-z0-9_.\-]*)["']""",
        r"""\bENV\s*\[\s*["']([A-Za-z_][A-Za-z0-9_.\-]*)["']\s*\]""",
        r"""\bENV\.fetch\s*\(\s*["']([A-Za-z_][A-Za-z0-9_.\-]*)["']""",
        r"""\b(?:std::)?env::(?:var|var_os)\s*\(\s*["']([A-Za-z_][A-Za-z0-9_.\-]*)["']""",
        r"""\bSystem\.getenv\s*\(\s*["']([A-Za-z_][A-Za-z0-9_.\-]*)["']""",
    )
)

VERDICT_RANK = {"TYPO": 0, "MISSING": 1, "GHOST": 2}
SUPPLY_SURFACES = frozenset({"declaration", "delivery"})


class ScanError(Exception):
    """An operational error that stops the scan. Exit code 2."""


class _Skip(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Options:
    root: str
    fmt: str = "text"
    out: str | None = None
    fail_on: str = "any"
    show_ok: bool = False
    exact: bool = False
    ignores: tuple[str, ...] = ()
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_files: int = DEFAULT_MAX_FILES
    max_depth: int = DEFAULT_MAX_DEPTH
    max_findings: int = DEFAULT_MAX_FINDINGS


@dataclass(frozen=True)
class Evidence:
    surface: str
    file: str
    line: int
    raw: str


@dataclass(frozen=True)
class Finding:
    verdict: str
    norm: str
    key: str
    suggestion: str | None
    suggestion_where: str | None
    explanation: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class Diagnostic:
    code: str
    file: str


@dataclass(frozen=True)
class ScanResult:
    root_label: str
    files_scanned: int
    keys_seen: int
    ok_count: int
    findings: tuple[Finding, ...]
    diagnostics: tuple[Diagnostic, ...]
    truncated: bool
    limits: dict[str, int]


# ---------------------------------------------------------------------------
# small pure helpers
# ---------------------------------------------------------------------------

def esc(value: str) -> str:
    """Neutralize terminal-hostile bytes while keeping them visible as text.

    Deleting a control sequence would hide tampering and make two distinct
    filenames render identically. Escaping keeps the evidence on screen.
    """
    out: list[str] = []
    for char in value:
        point = ord(char)
        if point < 32 or point == 127 or 0x80 <= point <= 0x9F:
            out.append("\\x%02x" % point)
        elif 0x202A <= point <= 0x202E or 0x2066 <= point <= 0x2069:
            out.append("\\u%04x" % point)
        else:
            out.append(char)
    return "".join(out)


def normalize(raw: str, exact: bool = False) -> str:
    """Join token. db.host, DB_HOST and db-host agree unless --exact."""
    if exact:
        return raw.strip()[:MAX_KEY_LEN]
    split = CAMEL_BOUNDARY.sub("_", raw.strip())
    return NON_ALNUM.sub("_", split.upper()).strip("_")[:MAX_KEY_LEN]


def _accepted(norm: str, ignored: frozenset[str]) -> bool:
    if len(norm) < 3 or len(norm) > MAX_KEY_LEN:
        return False
    if norm in ignored or norm in AMBIENT_KEYS:
        return False
    if not any(char.isalpha() for char in norm):
        return False
    return True


def levenshtein(left: str, right: str, cap: int = 2) -> int:
    """Bounded edit distance. Returns cap+1 as soon as the bound is exceeded."""
    if abs(len(left) - len(right)) > cap:
        return cap + 1
    if left == right:
        return 0
    previous = list(range(len(right) + 1))
    for i, lchar in enumerate(left, 1):
        current = [i]
        row_min = i
        for j, rchar in enumerate(right, 1):
            cost = 0 if lchar == rchar else 1
            value = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            current.append(value)
            if value < row_min:
                row_min = value
        if row_min > cap:
            return cap + 1
        previous = current
    return previous[-1] if previous[-1] <= cap else cap + 1


def _within(root: Path, candidate: Path) -> bool:
    try:
        return os.path.commonpath((str(root), str(candidate))) == str(root)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# filesystem walk
# ---------------------------------------------------------------------------

def _classify(rel: str) -> str:
    name = rel.rsplit("/", 1)[-1].lower()
    if name.startswith(".env") or name.endswith(".env"):
        return "env"
    if name == "dockerfile" or name.endswith(".dockerfile"):
        return "docker"
    if name.endswith((".yaml", ".yml")):
        return "workflow" if rel.startswith(".github/workflows/") else "yaml"
    if name.endswith(".json"):
        return "json"
    if name.endswith(".toml"):
        return "toml"
    if name.endswith((".ini", ".cfg")):
        return "ini"
    if name.endswith((".md", ".markdown", ".rst", ".txt")):
        return "doc"
    if name.endswith((".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
                      ".go", ".rb", ".rs", ".java", ".kt", ".sh", ".bash")):
        return "source"
    return "other"


def _read_bounded(path: Path, limit: int) -> str:
    with open(path, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise _Skip("not_regular")
        if info.st_size > limit:
            raise _Skip("too_large")
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise _Skip("too_large")
    return data.decode("utf-8", errors="replace")


def _walk(root: Path, options: Options) -> tuple[list[tuple[str, str, str]], list[Diagnostic]]:
    scanned: list[tuple[str, str, str]] = []
    diagnostics: list[Diagnostic] = []
    visited: set[tuple[int, int]] = set()
    root_stat = root.stat()
    visited.add((root_stat.st_dev, root_stat.st_ino))

    def visit(directory: Path, prefix: str, depth: int) -> None:
        if depth > options.max_depth:
            diagnostics.append(Diagnostic("max_depth_exceeded", prefix or "."))
            return
        if len(scanned) >= options.max_files:
            diagnostics.append(Diagnostic("max_files_reached", prefix or "."))
            return
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
        except (PermissionError, OSError, FileNotFoundError, NotADirectoryError):
            diagnostics.append(Diagnostic("unreadable_directory", prefix or "."))
            return
        for entry in entries:
            if len(scanned) >= options.max_files:
                diagnostics.append(Diagnostic("max_files_reached", prefix or "."))
                return
            rel = prefix + entry.name
            try:
                resolved = Path(entry.path).resolve(strict=False)
            except OSError:
                diagnostics.append(Diagnostic("unresolvable_path", rel))
                continue
            if not _within(root, resolved):
                diagnostics.append(Diagnostic("outside_root", rel))
                continue
            try:
                info = entry.stat(follow_symlinks=False)
            except (OSError, PermissionError):
                diagnostics.append(Diagnostic("unstatable_entry", rel))
                continue
            if stat.S_ISDIR(info.st_mode):
                if entry.name in EXCLUDED_DIRS:
                    continue
                inode = (info.st_dev, info.st_ino)
                if inode in visited:
                    diagnostics.append(Diagnostic("duplicate_inode", rel))
                    continue
                visited.add(inode)
                visit(Path(entry.path), rel + "/", depth + 1)
            elif stat.S_ISREG(info.st_mode):
                inode = (info.st_dev, info.st_ino)
                if inode in visited:
                    diagnostics.append(Diagnostic("duplicate_inode", rel))
                    continue
                visited.add(inode)
                kind = _classify(rel)
                if kind == "other":
                    continue
                try:
                    text = _read_bounded(Path(entry.path), options.max_file_bytes)
                except _Skip as skip:
                    diagnostics.append(Diagnostic(skip.code, rel))
                    continue
                except (OSError, PermissionError):
                    diagnostics.append(Diagnostic("unreadable_file", rel))
                    continue
                scanned.append((rel, kind, text))
            else:
                diagnostics.append(Diagnostic("non_regular", rel))

    visit(root, "", 0)
    return scanned, diagnostics


# ---------------------------------------------------------------------------
# surface parsers -- values are discarded here, never carried further
# ---------------------------------------------------------------------------

def _flatten_json(node: object, prefix: str, out: list[str], depth: int) -> None:
    if depth > MAX_JSON_DEPTH or len(out) >= MAX_KEYS_PER_FILE:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            if not isinstance(key, str) or len(out) >= MAX_KEYS_PER_FILE:
                continue
            joined = prefix + "." + key if prefix else key
            if isinstance(value, (dict, list)) and value:
                _flatten_json(value, joined, out, depth + 1)
            else:
                out.append(joined)
    elif isinstance(node, list):
        for item in node[:50]:
            if isinstance(item, (dict, list)):
                _flatten_json(item, prefix, out, depth + 1)


def _extract(kind: str, rel: str, text: str, options: Options) -> list[Evidence]:
    found: list[Evidence] = []
    lines = text.splitlines()

    def add(surface: str, raw: str, line: int) -> None:
        if len(found) < MAX_KEYS_PER_FILE and KEY_NAME.fullmatch(raw):
            found.append(Evidence(surface, rel, line, raw[:MAX_KEY_LEN]))

    if kind == "env":
        for number, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("export "):
                stripped = stripped[7:].lstrip()
            if "=" not in stripped:
                continue
            add("declaration", stripped.split("=", 1)[0].strip(), number)

    elif kind == "json":
        try:
            node = json.loads(text)
        except (ValueError, RecursionError):
            return found
        keys: list[str] = []
        _flatten_json(node, "", keys, 0)
        for key in keys:
            add("declaration", key, 1)

    elif kind in ("toml", "ini", "yaml", "workflow"):
        section = ""
        stack: list[tuple[int, str]] = []
        for number, line in enumerate(lines, 1):
            without_comment = line.split("#", 1)[0].rstrip()
            if kind in ("toml", "ini"):
                header = SECTION_HEADER.match(without_comment)
                if header:
                    section = header.group(1).strip()
                    stack = []
                    continue
            match = YAML_KEY.match(without_comment)
            if not match:
                continue
            raw, remainder = match.group(1), match.group(2).strip()
            if kind == "workflow" and raw.lower() in STRUCTURAL_WORDS:
                continue
            if kind == "yaml":
                indent = len(line) - len(line.lstrip(" \t"))
                while stack and stack[-1][0] >= indent:
                    stack.pop()
                if not remainder:
                    stack.append((indent, raw))
                    continue
                path = ".".join([name for _, name in stack] + [raw])
            else:
                if not remainder:
                    continue
                if kind in ("toml", "ini"):
                    path = section + "." + raw if section else raw
                else:
                    path = raw
            add("declaration", path, number)

    elif kind == "docker":
        for number, line in enumerate(lines, 1):
            stripped = line.strip()
            match = DOCKER_ENV.match(stripped)
            if not match:
                continue
            for token in match.group(1).split():
                if "=" in token:
                    add("delivery", token.split("=", 1)[0].strip(), number)

    elif kind == "doc":
        for number, line in enumerate(lines, 1):
            for match in DOC_KEY.finditer(line):
                add("documentation", match.group(1), number)

    elif kind == "source":
        for number, line in enumerate(lines, 1):
            for pattern in CONSUMPTION_PATTERNS:
                for match in pattern.finditer(line):
                    add("consumption", match.group(1), number)
                    if len(found) >= MAX_KEYS_PER_FILE:
                        return found
    return found


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------

def _evidence_dict(found: Iterable[Evidence], options: Options,
                   ignored: frozenset[str]) -> dict[str, list[Evidence]]:
    records: dict[str, list[Evidence]] = {}
    for item in found:
        norm = normalize(item.raw, options.exact)
        if not _accepted(norm, ignored):
            continue
        records.setdefault(norm, []).append(item)
    return records


def _analyze(records: dict[str, list[Evidence]], options: Options) -> tuple[list[Finding], int, int]:
    active = {
        norm: evidence
        for norm, evidence in records.items()
        if any(item.surface != "documentation" for item in evidence)
    }
    ok_count = 0
    issues: list[Finding] = []
    consumed_norms: list[str] = []

    for norm, evidence in active.items():
        supply = any(item.surface in SUPPLY_SURFACES for item in evidence)
        demand = any(item.surface == "consumption" for item in evidence)
        if supply and demand:
            ok_count += 1
        if demand:
            consumed_norms.append(norm)

    ghosts: list[str] = []
    for norm, evidence in active.items():
        supply = any(item.surface in SUPPLY_SURFACES for item in evidence)
        demand = any(item.surface == "consumption" for item in evidence)
        if supply and not demand:
            ghosts.append(norm)
        elif demand and not supply:
            issues.append(
                Finding(
                    "MISSING", norm, _representative(evidence), None, None,
                    "Read by source, never declared or delivered.",
                    _trim_evidence(evidence),
                )
            )

    for norm in ghosts:
        best: tuple[int, str] | None = None
        for candidate in consumed_norms:
            distance = levenshtein(norm, candidate, 1)
            if distance <= 1 and min(len(norm), len(candidate)) >= 4:
                if best is None or distance < best[0]:
                    best = (distance, candidate)
        evidence = active[norm]
        if best:
            target = active[best[1]]
            where = _first_consumption(target)
            issues.append(
                Finding(
                    "TYPO", norm, _representative(evidence),
                    _representative(target), where,
                    "Declared but never read. Matches a key the source does read: "
                    + _representative(target) + ".",
                    _trim_evidence(evidence),
                )
            )
        else:
            issues.append(
                Finding(
                    "GHOST", norm, _representative(evidence), None, None,
                    "Declared or delivered, never read by source.",
                    _trim_evidence(evidence),
                )
            )

    issues.sort(key=lambda item: (VERDICT_RANK[item.verdict], item.norm, item.key))
    return issues, ok_count, len(active)


def _representative(evidence: list[Evidence]) -> str:
    return sorted(evidence, key=lambda e: (e.file, e.line, e.surface, e.raw))[0].raw


def _trim_evidence(evidence: list[Evidence]) -> tuple[Evidence, ...]:
    ordered = sorted(evidence, key=lambda e: (e.file, e.line, e.surface, e.raw))
    return tuple(ordered[:MAX_EVIDENCE_PER_FINDING])


def _first_consumption(evidence: list[Evidence]) -> str:
    for item in sorted(evidence, key=lambda e: (e.file, e.line, e.surface)):
        if item.surface == "consumption":
            return item.file + ":" + str(item.line)
    return "unknown"


# ---------------------------------------------------------------------------
# renderers
# ---------------------------------------------------------------------------

def _finding_dict(finding: Finding) -> dict[str, object]:
    return {
        "verdict": finding.verdict,
        "key": finding.key,
        "normalized": finding.norm,
        "suggestion": finding.suggestion,
        "suggestion_where": finding.suggestion_where,
        "explanation": finding.explanation,
        "evidence": [
            {"surface": e.surface, "file": e.file, "line": e.line}
            for e in finding.evidence
        ],
    }


def render_json(result: ScanResult) -> str:
    counts = _counts(result)
    payload = {
        "schema": SCHEMA,
        "tool": {"name": "ghostkey", "version": VERSION},
        "root": result.root_label,
        "scan": {
            "files": result.files_scanned,
            "keys": result.keys_seen,
            "ok": result.ok_count,
            **counts,
            "diagnostics": len(result.diagnostics),
            "truncated": result.truncated,
        },
        "limits": result.limits,
        "findings": [_finding_dict(f) for f in result.findings],
        "diagnostics": [{"code": d.code, "file": d.file} for d in result.diagnostics],
    }
    return json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n"


def render_sarif(result: ScanResult) -> str:
    rules = [
        {"id": "GK_TYPO", "name": "TypoPair", "shortDescription": {"text": "Declared key looks like a typo of a consumed key"}},
        {"id": "GK_MISSING", "name": "MissingKey", "shortDescription": {"text": "Consumed key has no declaration or delivery"}},
        {"id": "GK_GHOST", "name": "GhostKey", "shortDescription": {"text": "Declared key is never read"}},
    ]
    results = []
    for finding in result.findings:
        location = finding.evidence[0] if finding.evidence else None
        entry = {
            "ruleId": "GK_" + finding.verdict,
            "level": "warning" if finding.verdict == "GHOST" else "error",
            "message": {"text": finding.explanation},
        }
        if location is not None:
            entry["locations"] = [{
                "physicalLocation": {
                    "artifactLocation": {"uri": location.file},
                    "region": {"startLine": location.line},
                }
            }]
        results.append(entry)
    payload = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{
            "tool": {"driver": {"name": "ghostkey", "version": VERSION, "rules": rules}},
            "results": results,
        }],
    }
    return json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n"


def render_text(result: ScanResult, options: Options) -> str:
    counts = _counts(result)
    out: list[str] = []
    out.append("ghostkey %s  |  %s  |  %d files  |  %d keys" % (
        VERSION, esc(result.root_label), result.files_scanned, result.keys_seen))
    out.append("")
    if not result.findings and not options.show_ok:
        out.append("  No ghost, missing or typo keys found.")
    else:
        out.append("  %-28s %-8s %s" % ("KEY", "VERDICT", "EVIDENCE"))
        out.append("  " + "-" * 72)
        for finding in result.findings:
            where = finding.evidence[0] if finding.evidence else None
            location = esc(where.file + ":" + str(where.line)) if where else "-"
            out.append("  %-28s %-8s %s" % (
                esc(_clip(finding.key, 28)), finding.verdict, location))
            out.append("      " + esc(_clip(finding.explanation, 90)))
            if finding.suggestion:
                out.append("      did you mean %s (%s)?" % (
                    esc(_clip(finding.suggestion, 40)),
                    esc(finding.suggestion_where or "unknown")))
        if options.show_ok:
            out.append("  %d keys have both supply and demand." % result.ok_count)
    out.append("")
    out.append("  %d typo  %d missing  %d ghost  %d ok  %d diagnostics%s" % (
        counts["typo"], counts["missing"], counts["ghost"], result.ok_count,
        len(result.diagnostics), "  [truncated]" if result.truncated else ""))
    if result.diagnostics and options.show_ok:
        out.append("")
        for diagnostic in result.diagnostics[:10]:
            out.append("  %s  %s" % (diagnostic.code, esc(_clip(diagnostic.file, 60))))
    return "\n".join(out) + "\n"


def _clip(value: str, size: int) -> str:
    return value if len(value) <= size else value[: size - 3] + "..."


def _counts(result: ScanResult) -> dict[str, int]:
    counts = {"ghost": 0, "typo": 0, "missing": 0}
    for finding in result.findings:
        counts[finding.verdict.lower()] += 1
    return counts


def render(result: ScanResult, options: Options) -> str:
    if options.fmt == "json":
        return render_json(result)
    if options.fmt == "sarif":
        return render_sarif(result)
    return render_text(result, options)


def decide_exit(result: ScanResult, options: Options) -> int:
    if options.fail_on == "none" or not result.findings:
        return 0
    if options.fail_on == "any":
        return 1
    return 1 if any(f.verdict == options.fail_on.upper() for f in result.findings) else 0


# ---------------------------------------------------------------------------
# public interface
# ---------------------------------------------------------------------------

def run(options: Options) -> ScanResult:
    try:
        root = Path(options.root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ScanError("cannot resolve root: " + type(exc).__name__) from exc
    if not root.is_dir():
        raise ScanError("root is not a directory")

    ignored = frozenset(normalize(item, options.exact) for item in options.ignores)
    scanned, diagnostics = _walk(root, options)

    all_evidence: list[Evidence] = []
    for rel, kind, text in scanned:
        all_evidence.extend(_extract(kind, rel, text, options))
    records = _evidence_dict(all_evidence, options, ignored)
    findings, ok_count, keys_seen = _analyze(records, options)

    truncated = len(findings) > options.max_findings
    if truncated:
        findings = findings[: options.max_findings]

    diagnostics.sort(key=lambda item: (item.file, item.code))
    return ScanResult(
        root_label=root.name or ".",
        files_scanned=len(scanned),
        keys_seen=keys_seen,
        ok_count=ok_count,
        findings=tuple(findings),
        diagnostics=tuple(diagnostics),
        truncated=truncated,
        limits={
            "max_file_bytes": options.max_file_bytes,
            "max_files": options.max_files,
            "max_depth": options.max_depth,
            "max_findings": options.max_findings,
        },
    )
