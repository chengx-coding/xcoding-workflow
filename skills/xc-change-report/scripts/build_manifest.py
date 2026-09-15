#!/usr/bin/env python3
"""Build the `xc-change-report` coverage manifest from a real worktree and a real baseline.

This module also owns the shared constants and the shared code-block normalisation
implementation that `build_skeleton.py` and `validate_report.py` import, so the
forward direction (rendering a unit code block) and the reverse direction
(recomputing its hash) can never drift apart.

Standard library only.
"""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

# --------------------------------------------------------------------------------------
# Contract constants. Every value here is mirrored in
# `references/change-report-contract.md` and `references/coverage-protocol.md`.
# --------------------------------------------------------------------------------------

SCHEMA_VERSION = 1
ENUMERATION_VERSION = "xc-change-report/enumeration/v1"
NORMALIZATION_VERSION = "code-block/v1"
DIGEST_ALGORITHM = "sha256(path-nul-contenthash-lf/v1)"
SOURCE_HASH_ALGORITHM = "sha256(raw-bytes)"
PROVENANCE_ALGORITHM = "three-point-diff/v1"
REDACTION_MARKER = "<<redacted:sha256={hash}>>"

# Analysis thresholds (A13).
FIELD_NAMES = (
    "what",
    "why",
    "design",
    "tradeoffs",
    "flow-position",
    "alternatives",
    "business-process",
    "data-and-control",
)
MIN_FIELD_CHARS = 40
PLACEHOLDER_TOKENS = (
    "todo",
    "tbd",
    "fixme",
    "n/a",
    "xxx",
    "placeholder",
    "lorem ipsum",
    "待补充",
    "待定",
)
SYMBOL_ONLY_RE = re.compile(r"^[^\w]+$", re.UNICODE)

# Unit-window constants (C31) and strength constants.
MAX_ADDED_UNIT_LINES = 400
ADDED_UNIT_BLOCK_LINES = 200
MAX_UNITS_MINIMAL = 5
MAX_UNIT_LINES_SNIPPET = 60

STRENGTHS = ("minimal", "standard", "full")
REPORT_GATE_OUTCOMES = ("accepted", "revision-required", "rejected", "accepted-with-followup")
GATE_OUTCOME_KEY = "report.gate_outcome"
REWORK_KEY = "report.gate_rework_required"
RECOVERY_KEY = "report.gate_recovery_required"

# Accuracy review thresholds.
MAX_WRONG = 0
MAX_MISLEADING = 0
VERDICTS = ("accurate", "misleading", "wrong")

# Exclusion categories (C15) -- a closed enumeration.
EXCLUSION_CATEGORIES = (
    "generated",
    "lockfile",
    "vendor",
    "binary",
    "minified",
    "sensitive",
    "encoding_unsupported",
    "pre_existing_change",
)

CHANGE_KINDS = ("added", "modified", "deleted", "renamed")
ANALYZED_AS = ("work_order", "pre_existing", "mixed")
PROVENANCE_VALUES = ("work_order", "pre_existing")
PRESENTATIONS = ("snippet", "diff")

# Diagram contract (D9, D14-D17).
DIAGRAM_TYPES = ("flow", "sequence", "class", "er", "state")
SVG_RENDER_TYPES = ("flow", "state")
TABLE_RENDER_TYPES = ("sequence", "class", "er")
MAX_TEXT_NODE_CHARS = 40
MAX_SVG_CANVAS_WIDTH = 1400
MAX_SVG_CANVAS_HEIGHT = 1400
MIN_SVG_FONT_SIZE = 11
SVG_FONT_SIZE = 12
SVG_NODE_WIDTH = 220
SVG_NODE_HEIGHT = 46
SVG_NODE_GAP = 40
SVG_LAYER_GAP = 90
SVG_MARGIN = 24
SVG_CHAR_WIDTH = 7
TABLE_CELL_CHARS = 120

# Sensitive detection (C34).
SENSITIVE_PATH_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.jks",
    "*.keystore",
    "id_rsa*",
    "id_ed25519*",
    "*.kdbx",
    "credentials*",
    "secrets*",
    "*secret*.json",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "*_rsa",
    "*service-account*.json",
)
SENSITIVE_CONTENT_PATTERNS = (
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "pem_private_key_header"),
    (r"-----BEGIN OPENSSH PRIVATE KEY-----", "openssh_private_key_header"),
    (r"\bghp_[A-Za-z0-9]{16,}", "github_token_prefix"),
    (r"\bgithub_pat_[A-Za-z0-9_]{16,}", "github_pat_prefix"),
    (r"\bAKIA[0-9A-Z]{12,}", "aws_access_key_prefix"),
    (r"\bxox[baprs]-[A-Za-z0-9-]{10,}", "slack_token_prefix"),
)

# Deterministic path-based exclusions (C14, C15, C17).
GENERATED_PATTERNS = (
    "*.pb.go",
    "*_pb2.py",
    "*_pb2_grpc.py",
    "*.generated.*",
    "*.gen.*",
    "*.designer.cs",
    "*.g.cs",
    "*.g.dart",
    "generated/*",
    "*/generated/*",
    "__generated__/*",
    "*/__generated__/*",
)
LOCKFILE_NAMES = (
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pipfile.lock",
    "cargo.lock",
    "composer.lock",
    "gemfile.lock",
    "go.sum",
    "uv.lock",
)
VENDOR_PATTERNS = (
    "vendor/*",
    "*/vendor/*",
    "node_modules/*",
    "*/node_modules/*",
    "third_party/*",
    "*/third_party/*",
)
MINIFIED_PATTERNS = ("*.min.js", "*.min.css", "*.min.mjs", "*.min.*")

# Code-block markup contract (H25, H26a, H28).
CODE_BLOCK_CLASS = "report-code"
CODE_CONTEXT_CLASS = "report-code-context"
CODE_LINENO_CLASS = "report-lineno"
CODE_LINE_CLASS = "report-line"
CODE_CHANGED_CLASS = "report-code-changed"
DIFF_HEAD_CLASS = "report-diff-head"
DIFF_ADD_CLASS = "report-diff-add"
DIFF_DEL_CLASS = "report-diff-del"
ANCHOR_CLASS = "report-anchor"
UNIT_FIELD_CLASS = "report-unit-field"
CODE_LINE_SEPARATOR = "\t"
CODE_EXCLUSION_CLASSES = (
    CODE_BLOCK_CLASS,
    CODE_CHANGED_CLASS,
    CODE_CONTEXT_CLASS,
    DIFF_ADD_CLASS,
    DIFF_DEL_CLASS,
)

SECTION_IDS = (
    "section-overview",
    "section-change-map",
    "section-process-position",
    "section-units",
    "section-related-code",
    "section-diagrams",
    "section-verification",
    "section-glossary",
    "section-report-info",
)

HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
LINENO_PREFIX_RE = re.compile(r"^\d+" + re.escape(CODE_LINE_SEPARATOR))


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_text(lines: Iterable[str]) -> str:
    """Canonical unit text: one trailing newline per kept line (H26a)."""
    return "".join(line + "\n" for line in lines)


def content_sha256(lines: Iterable[str]) -> str:
    return sha256_hex(canonical_text(lines).encode("utf-8"))


def range_object(start: int, count: int) -> dict[str, int]:
    """A line range; `end < start` marks an empty range."""
    if count <= 0:
        return {"start": start + 1, "end": start}
    return {"start": start, "end": start + count - 1}


def range_is_empty(line_range: dict[str, Any]) -> bool:
    return int(line_range["end"]) < int(line_range["start"])


def range_length(line_range: dict[str, Any]) -> int:
    return max(0, int(line_range["end"]) - int(line_range["start"]) + 1)


def slice_lines(lines: list[str], line_range: dict[str, Any]) -> list[str]:
    if range_is_empty(line_range):
        return []
    return lines[int(line_range["start"]) - 1 : int(line_range["end"])]


def file_slug(path: str) -> str:
    """H22: lowercase, map separators and non-alphanumerics to `-`, collapse runs."""
    lowered = path.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    return slug.strip("-")


def format_range(path: str, line_range: dict[str, Any]) -> str:
    return f"{path}:{int(line_range['start'])}-{int(line_range['end'])}"


def sort_key(path: str) -> bytes:
    return path.encode("utf-8", "replace")


def split_lines(text: str) -> list[str]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def decode_content(payload: bytes) -> tuple[str, bool]:
    """Strict UTF-8 first; fall back to replacement decoding (C36)."""
    try:
        return payload.decode("utf-8"), False
    except UnicodeDecodeError:
        return payload.decode("utf-8", "replace"), True


def looks_binary(payload: bytes) -> bool:
    return b"\x00" in payload[:8192]


def is_unusable_decoded_text(text: str) -> bool:
    return text.replace("\ufffd", "").strip() == ""


def match_any_pattern(name: str, patterns: Iterable[str]) -> bool:
    lowered = name.lower()
    return any(fnmatch.fnmatchcase(lowered, pattern.lower()) for pattern in patterns)


def sensitive_path_hit(path: str) -> str:
    """Return the matched credential pattern, or an empty string (C34 rule 1)."""
    for segment in path.split("/"):
        if not segment:
            continue
        for pattern in SENSITIVE_PATH_PATTERNS:
            if fnmatch.fnmatchcase(segment.lower(), pattern.lower()):
                return pattern
    return ""


def sensitive_content_hits(text: str) -> list[str]:
    return [label for pattern, label in SENSITIVE_CONTENT_PATTERNS if re.search(pattern, text)]


def sensitive_line_hit(line: str) -> bool:
    return bool(sensitive_content_hits(line))


def redaction_marker(line: str) -> str:
    return REDACTION_MARKER.format(hash=sha256_hex(line.encode("utf-8"))[:12])


def file_exclusion_reason(path: str, payload: bytes | None, text: str, encoding_unsupported: bool) -> str:
    """Deterministic file-level exclusion classification (C14, C15, C17, C34, C36)."""
    if payload is None:
        return ""
    if looks_binary(payload):
        return "binary"
    if sensitive_path_hit(path) or sensitive_content_hits(text):
        return "sensitive"
    if match_any_pattern(path, GENERATED_PATTERNS):
        return "generated"
    if os.path.basename(path).lower() in LOCKFILE_NAMES:
        return "lockfile"
    if match_any_pattern(path, VENDOR_PATTERNS):
        return "vendor"
    if match_any_pattern(path, MINIFIED_PATTERNS):
        return "minified"
    if encoding_unsupported and is_unusable_decoded_text(text):
        return "encoding_unsupported"
    return ""


def export_ignore_patterns(repo: Path) -> list[str]:
    """Minimal `.gitattributes` reader for the `export-ignore` attribute (C34 rule 2)."""
    attributes = repo / ".gitattributes"
    if not attributes.is_file():
        return []
    patterns: list[str] = []
    for raw in attributes.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and "export-ignore" in parts[1:]:
            patterns.append(parts[0])
    return patterns


# --------------------------------------------------------------------------------------
# Shared code-block implementation (H26a) -- imported by build_skeleton.py and
# validate_report.py as well.
# --------------------------------------------------------------------------------------


def _line_kind(classes: list[str]) -> str:
    if DIFF_HEAD_CLASS in classes:
        return "head"
    if DIFF_DEL_CLASS in classes:
        return "del"
    if DIFF_ADD_CLASS in classes:
        return "add"
    if CODE_CHANGED_CLASS in classes:
        return "chg"
    return "ctx"


def render_code_line(kind: str, lineno: int | str, payload_html: str) -> str:
    classes = [CODE_LINE_CLASS, f"{CODE_LINE_CLASS}-{kind}"]
    if kind == "head":
        classes.append(DIFF_HEAD_CLASS)
    elif kind == "del":
        classes.append(DIFF_DEL_CLASS)
    elif kind == "add":
        classes.extend([DIFF_ADD_CLASS, CODE_CHANGED_CLASS])
    elif kind == "chg":
        classes.append(CODE_CHANGED_CLASS)
    lineno_html = f'<span class="{CODE_LINENO_CLASS}">{lineno}</span>'
    return (
        f'<span class="{" ".join(classes)}">'
        f"{lineno_html}{CODE_LINE_SEPARATOR}{payload_html}</span>"
    )


def render_code_rows(rows: list[tuple[str, int | str, str]]) -> str:
    return "".join(render_code_line(kind, lineno, payload) + "\n" for kind, lineno, payload in rows)


class _CodeBlockNormalizer(HTMLParser):
    """Collects the text of every `report-line` element inside a code block."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[tuple[str, str]] = []
        self._tags: list[str] = []
        self._frames: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tags.append(tag)
        class_attr = ""
        for name, value in attrs:
            if name == "class" and value:
                class_attr = value
        classes = class_attr.split()
        if CODE_LINE_CLASS in classes:
            self._frames.append({"kind": _line_kind(classes), "buf": [], "depth": len(self._tags)})

    def handle_endtag(self, tag: str) -> None:
        if self._frames and len(self._tags) == self._frames[-1]["depth"]:
            frame = self._frames.pop()
            self.lines.append((frame["kind"], "".join(frame["buf"])))
        if self._tags:
            self._tags.pop()

    def handle_data(self, data: str) -> None:
        if self._frames:
            self._frames[-1]["buf"].append(data)


def normalize_code_text(inner_html: str) -> str:
    """H26a normalisation: line-number column, changed markers and diff markers removed.

    Dropping `report-diff-del` rows and the single leading `+` of `report-diff-add`
    rows is what makes the snippet presentation and the unified-diff presentation
    reduce to the same text (H27).
    """
    parser = _CodeBlockNormalizer()
    parser.feed(inner_html)
    parser.close()
    kept: list[str] = []
    for kind, raw in parser.lines:
        if kind in {"head", "del"}:
            continue
        text = LINENO_PREFIX_RE.sub("", raw, count=1)
        if kind == "add" and text.startswith("+"):
            text = text[1:]
        kept.append(text)
    return canonical_text(kept)


# --------------------------------------------------------------------------------------
# Git plumbing
# --------------------------------------------------------------------------------------


class ManifestError(RuntimeError):
    pass


def _git_command(args: list[str]) -> list[str]:
    return ["git", "-c", "core.quotepath=false", *args]


def run_git(repo: Path, args: list[str], allow_one: bool = False) -> bytes:
    proc = subprocess.run(_git_command(args), cwd=str(repo), capture_output=True)
    allowed = (0, 1) if allow_one else (0,)
    if proc.returncode not in allowed:
        raise ManifestError(
            "git command failed: "
            + " ".join(_git_command(args))
            + " :: "
            + proc.stderr.decode("utf-8", "replace").strip()
        )
    return proc.stdout


def git_ok(repo: Path, args: list[str]) -> bool:
    return subprocess.run(_git_command(args), cwd=str(repo), capture_output=True).returncode == 0


def resolve_repo(repo: Path) -> Path:
    if not repo.is_dir():
        raise ManifestError(f"repository path does not exist: {repo}")
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(repo), capture_output=True)
    if proc.returncode != 0:
        raise ManifestError(f"not a git working tree: {repo}")
    return Path(proc.stdout.decode("utf-8", "replace").strip())


def require_commit(repo: Path, commit: str) -> None:
    if not git_ok(repo, ["cat-file", "-e", f"{commit}^{{commit}}"]):
        raise ManifestError(f"baseline commit is not resolvable: {commit}")


def tracked_paths(repo: Path, commit: str) -> set[str]:
    payload = run_git(repo, ["ls-tree", "-r", "--name-only", "-z", commit])
    return {item.decode("utf-8", "replace") for item in payload.split(b"\x00") if item}


def name_status(repo: Path, commit: str) -> dict[str, str]:
    payload = run_git(repo, ["diff", "--no-renames", "--name-status", "-z", commit, "--"])
    fields = payload.split(b"\x00")
    result: dict[str, str] = {}
    index = 0
    while index + 1 < len(fields):
        raw_status = fields[index].decode("utf-8", "replace")
        path = fields[index + 1].decode("utf-8", "replace")
        index += 2
        if not raw_status or not path:
            continue
        status = raw_status[0]
        result[path] = {"A": "added", "D": "deleted"}.get(status, "modified")
    return result


def untracked_paths(repo: Path) -> list[str]:
    payload = run_git(repo, ["ls-files", "--others", "--exclude-standard", "-z"])
    return sorted(
        (item.decode("utf-8", "replace") for item in payload.split(b"\x00") if item), key=sort_key
    )


def git_show_bytes(repo: Path, commit: str, path: str) -> bytes | None:
    proc = subprocess.run(
        _git_command(["show", f"{commit}:{path}"]), cwd=str(repo), capture_output=True
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def snapshot_bytes(directory: Path | None, path: str) -> bytes | None:
    if directory is None or not directory.is_dir():
        return None
    return read_bytes(directory / Path(path))


def snapshot_dir(manifest: dict[str, Any]) -> Path | None:
    """The recorded baseline untracked-snapshot directory, or None when unset."""
    raw = str(manifest.get("baseline", {}).get("untracked_snapshot", {}).get("path", "") or "")
    return Path(raw) if raw else None


def snapshot_paths(directory: Path | None) -> list[str]:
    """Every relative path captured in a baseline snapshot directory (C4a)."""
    if directory is None or not directory.is_dir():
        return []
    return sorted(
        (item.relative_to(directory).as_posix() for item in directory.rglob("*") if item.is_file()),
        key=sort_key,
    )


def split_hunks(payload: str) -> list[dict[str, Any]]:
    """Parse unified diff output into hunks with row-aware changed-line tracking."""
    hunks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in payload.split("\n"):
        if line.startswith("@@ "):
            match = HUNK_HEADER_RE.match(line)
            current = None
            if not match:
                continue
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) is not None else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) is not None else 1
            current = {
                "old_range": range_object(old_start, old_count),
                "new_range": range_object(new_start, new_count),
                "_rows": [],
            }
            hunks.append(current)
            continue
        if current is None or line.startswith("\\"):
            continue
        if line.startswith("+"):
            current["_rows"].append("add")
        elif line.startswith("-"):
            current["_rows"].append("del")
        elif line.startswith(" "):
            current["_rows"].append("ctx")
    for hunk in hunks:
        hunk["rows"] = list(hunk["_rows"])
        hunk["changed_new_lines"] = _changed_new_lines(hunk)
        hunk["changed_old_lines"] = _changed_old_lines(hunk)
        hunk.pop("_rows", None)
    return hunks


def _changed_new_lines(hunk: dict[str, Any]) -> list[int]:
    numbers: list[int] = []
    new_line = int(hunk["new_range"]["start"])
    for row in hunk["_rows"]:
        if row == "add":
            numbers.append(new_line)
            new_line += 1
        elif row == "ctx":
            new_line += 1
    return numbers


def _changed_old_lines(hunk: dict[str, Any]) -> list[int]:
    numbers: list[int] = []
    old_line = int(hunk["old_range"]["start"])
    for row in hunk["_rows"]:
        if row == "del":
            numbers.append(old_line)
            old_line += 1
        elif row == "ctx":
            old_line += 1
    return numbers


def diff_tracked_path(repo: Path, commit: str, path: str) -> list[dict[str, Any]]:
    payload = run_git(
        repo,
        [
            "diff",
            "--no-renames",
            "--no-color",
            "--diff-algorithm=myers",
            "--unified=3",
            commit,
            "--",
            path,
        ],
    ).decode("utf-8", "replace")
    return split_hunks(payload)


def diff_no_index(left: bytes, right: bytes, unified: int, tmp: Path) -> list[dict[str, Any]]:
    left_path = tmp / "no-index-left.tmp"
    right_path = tmp / "no-index-right.tmp"
    left_path.write_bytes(left)
    right_path.write_bytes(right)
    proc = subprocess.run(
        _git_command(
            [
                "diff",
                "--no-index",
                "--no-color",
                "--diff-algorithm=myers",
                f"--unified={unified}",
                "--",
                str(left_path),
                str(right_path),
            ]
        ),
        capture_output=True,
    )
    if proc.returncode not in (0, 1):
        raise ManifestError(
            "git diff --no-index failed: " + proc.stderr.decode("utf-8", "replace").strip()
        )
    return split_hunks(proc.stdout.decode("utf-8", "replace"))


# --------------------------------------------------------------------------------------
# Enumeration helpers
# --------------------------------------------------------------------------------------


def block_units(lines: list[str]) -> list[dict[str, int]]:
    """Deterministic window splitting for whole-file added/deleted units (C31)."""
    total = len(lines)
    if total == 0:
        return [{"start": 1, "end": 0}]
    if total <= MAX_ADDED_UNIT_LINES:
        return [{"start": 1, "end": total}]
    units: list[dict[str, int]] = []
    start = 1
    while start <= total:
        end = min(start + ADDED_UNIT_BLOCK_LINES - 1, total)
        units.append({"start": start, "end": end})
        start = end + 1
    return units


def ranges_intersect(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if range_is_empty(left) or range_is_empty(right):
        return False
    return int(left["start"]) <= int(right["end"]) and int(right["start"]) <= int(left["end"])


def merge_ranges(ranges: list[dict[str, Any]]) -> list[dict[str, int]]:
    merged: list[dict[str, int]] = []
    for item in sorted(
        (r for r in ranges if not range_is_empty(r)), key=lambda r: (int(r["start"]), int(r["end"]))
    ):
        if merged and int(item["start"]) <= int(merged[-1]["end"]) + 1:
            merged[-1]["end"] = max(int(merged[-1]["end"]), int(item["end"]))
        else:
            merged.append({"start": int(item["start"]), "end": int(item["end"])})
    return merged


def map_old_range_to_new(old_range: dict[str, Any], work_order_hunks: list[dict[str, Any]]) -> dict[str, int] | None:
    """Map a baseline-snapshot(B)-side range into head(H) coordinates.

    Returns None when the range falls inside a work-order-changed region, which the
    contract resolves conservatively as an overlap (C37 step 4).
    """
    if range_is_empty(old_range):
        return {"start": 0, "end": -1}
    offset = 0
    for hunk in sorted(work_order_hunks, key=lambda h: int(h["old_range"]["start"])):
        hunk_old = hunk["old_range"]
        hunk_new = hunk["new_range"]
        if range_is_empty(hunk_old):
            if int(hunk_old["start"]) <= int(old_range["start"]):
                offset += range_length(hunk_new)
            continue
        if int(hunk_old["end"]) < int(old_range["start"]):
            offset += range_length(hunk_new) - range_length(hunk_old)
            continue
        if int(hunk_old["start"]) > int(old_range["end"]):
            break
        return None
    return {"start": int(old_range["start"]) + offset, "end": int(old_range["end"]) + offset}


def classify_provenance(
    head_range: dict[str, Any],
    pre_existing_ranges: list[dict[str, Any]],
    work_order_ranges: list[dict[str, Any]],
) -> tuple[str, bool]:
    pre_hit = any(ranges_intersect(head_range, item) for item in pre_existing_ranges)
    work_hit = any(ranges_intersect(head_range, item) for item in work_order_ranges)
    if not pre_hit:
        return "work_order", False
    if not work_hit:
        return "pre_existing", False
    return "work_order", True


def compute_provenance_ranges(
    old_bytes: bytes, baseline_bytes: bytes, head_bytes: bytes, tmp: Path
) -> tuple[list[dict[str, int]], list[dict[str, int]], str]:
    """C37 three-point alignment; returns (pre-existing H ranges, work-order H ranges, note)."""
    for payload in (old_bytes, baseline_bytes, head_bytes):
        if looks_binary(payload):
            return [], [], "binary"
        _, bad = decode_content(payload)
        if bad:
            return [], [], "decode_failure"
    pre_existing_hunks = diff_no_index(old_bytes, baseline_bytes, 0, tmp)
    work_order_hunks = diff_no_index(baseline_bytes, head_bytes, 0, tmp)
    pre_existing_ranges: list[dict[str, int]] = []
    work_order_ranges = [
        {"start": int(item["new_range"]["start"]), "end": int(item["new_range"]["end"])}
        for item in work_order_hunks
        if not range_is_empty(item["new_range"])
    ]
    for hunk in pre_existing_hunks:
        mapped = map_old_range_to_new(hunk["new_range"], work_order_hunks)
        if mapped is None:
            pre_existing_ranges.extend(dict(item) for item in work_order_ranges)
            continue
        pre_existing_ranges.append(mapped)
    return merge_ranges(pre_existing_ranges), merge_ranges(work_order_ranges), ""


def choose_presentation(hunk: dict[str, Any]) -> str:
    if hunk["content_side"] == "old":
        return "snippet"
    changed = hunk.get("changed_new_lines", [])
    if range_length(hunk["new_range"]) > MAX_UNIT_LINES_SNIPPET:
        return "diff"
    if changed:
        contiguous = changed == list(range(min(changed), max(changed) + 1))
        if not contiguous:
            return "diff"
        if len(changed) < range_length(hunk["new_range"]):
            return "diff"
    return "snippet"


def unit_lines(
    repo: Path,
    commit: str,
    untracked_snapshot: Path | None,
    entry: dict[str, Any],
    hunk: dict[str, Any],
) -> list[str]:
    """Canonical text lines for a unit (shared by build_manifest and build_skeleton)."""
    line_range = hunk["new_range"] if hunk["content_side"] == "new" else hunk["old_range"]
    if hunk["content_side"] == "new":
        payload = read_bytes(repo / Path(entry["path"])) or b""
    elif entry.get("baseline_source") == "untracked_snapshot":
        payload = snapshot_bytes(untracked_snapshot, entry["path"]) or b""
    else:
        payload = git_show_bytes(repo, commit, entry["path"]) or b""
    text, _ = decode_content(payload)
    return slice_lines(split_lines(text), line_range)


def unit_canonical_lines(lines: list[str], hunk: dict[str, Any]) -> list[str]:
    """Apply the redaction rule (C35) to a unit's canonical text lines."""
    if not hunk.get("redacted"):
        return lines
    return [redact_line(line) for line in lines]


def redact_line(line: str) -> str:
    """Replace one secret-shaped line by the fixed redaction marker (C35)."""
    return redaction_marker(line) if sensitive_line_hit(line) else line


def baseline_lines_for(
    repo: Path, commit: str, untracked_snapshot: Path | None, entry: dict[str, Any]
) -> list[str]:
    if entry.get("baseline_source") == "untracked_snapshot":
        payload = snapshot_bytes(untracked_snapshot, entry["path"]) or b""
    else:
        payload = git_show_bytes(repo, commit, entry["path"]) or b""
    return split_lines(decode_content(payload)[0])


def rendered_old_lines(
    repo: Path,
    commit: str,
    untracked_snapshot: Path | None,
    entry: dict[str, Any],
    hunk: dict[str, Any],
) -> list[str]:
    """Baseline-side lines that the unified-diff presentation actually prints."""
    if hunk.get("presentation") == "diff":
        numbers = hunk.get("changed_old_lines", [])
        if not numbers:
            return []
        lines = baseline_lines_for(repo, commit, untracked_snapshot, entry)
        return [lines[number - 1] for number in numbers if 0 < number <= len(lines)]
    if hunk.get("content_side") == "old":
        return unit_lines(repo, commit, untracked_snapshot, entry, hunk)
    return []


# --------------------------------------------------------------------------------------
# Manifest construction
# --------------------------------------------------------------------------------------


def digest_from_hashes(pairs: list[tuple[str, str]]) -> str:
    payload = bytearray()
    for path, digest in sorted(pairs, key=lambda item: sort_key(item[0])):
        payload.extend(path.encode("utf-8", "replace"))
        payload.extend(b"\x00")
        payload.extend(digest.encode("ascii"))
        payload.extend(b"\n")
    return sha256_hex(bytes(payload))


def head_digest(repo: Path, paths: list[str]) -> str:
    """Recompute the head digest from the current worktree (shared with the validator)."""
    pairs: list[tuple[str, str]] = []
    for path in paths:
        payload = read_bytes(repo / Path(path))
        pairs.append((path, sha256_hex(payload if payload is not None else b"")))
    return digest_from_hashes(pairs)


def build_file_entry(
    repo: Path,
    commit: str,
    untracked_snapshot: Path | None,
    tmp: Path,
    path: str,
    change_kind: str,
    commit_bytes: bytes | None,
    baseline_bytes: bytes | None,
    head_bytes: bytes | None,
    baseline_source: str,
    worktree_snapshot_available: bool,
    notes: list[str],
) -> dict[str, Any]:
    """Build one `files[]` entry.

    `commit_bytes` is the baseline-commit content (O), `baseline_bytes` the work-order
    opening snapshot content (B) and `head_bytes` the current worktree content (H).
    The change kind and the hunks are taken from the O -> H diff, exactly as the
    enumeration algorithm prescribes; provenance then splits that diff into the
    pre-existing side (O -> B) and the work-order side (B -> H) (C37).
    """
    head_payload = head_bytes if head_bytes is not None else b""
    origin_payload = commit_bytes if commit_bytes is not None else baseline_bytes
    classification_payload = (
        head_bytes if head_bytes is not None else (baseline_bytes if baseline_bytes is not None else origin_payload)
    )
    classification_text, classification_bad = decode_content(classification_payload or b"")
    head_text, head_bad = decode_content(head_payload)
    encoding_unsupported = head_bad or classification_bad
    exclusion = file_exclusion_reason(
        path,
        classification_payload if classification_payload is not None else None,
        classification_text,
        classification_bad,
    )

    entry: dict[str, Any] = {
        "path": path,
        "change_kind": change_kind,
        "renamed_from": "",
        "baseline_present": commit_bytes is not None,
        "head_present": head_bytes is not None,
        "analyzable": exclusion == "",
        "exclude_reason": exclusion,
        "analyzed_as": "work_order",
        "source_sha256": sha256_hex(head_payload),
        "origin_sha256": sha256_hex(origin_payload if origin_payload is not None else b""),
        "baseline_sha256": sha256_hex(baseline_bytes if baseline_bytes is not None else b""),
        "source_algorithm": SOURCE_HASH_ALGORITHM,
        "encoding_unsupported": encoding_unsupported,
        "baseline_source": baseline_source,
        "provenance_degraded": not worktree_snapshot_available,
        "sensitive_path_pattern": sensitive_path_hit(path),
        "hunks": [],
    }
    if exclusion:
        return entry

    baseline_text, _ = decode_content(baseline_bytes or b"")
    head_lines = split_lines(head_text)
    baseline_lines = split_lines(baseline_text)

    hunks: list[dict[str, Any]] = []
    if change_kind in {"added", "deleted"}:
        source_lines = head_lines if change_kind == "added" else split_lines(
            decode_content(origin_payload or b"")[0]
        )
        for block in block_units(source_lines):
            if change_kind == "added":
                old_range: dict[str, int] = {"start": 1, "end": 0}
                new_range: dict[str, int] = dict(block)
                content_side = "new"
                changed_new = list(range(block["start"], block["end"] + 1)) if not range_is_empty(block) else []
                changed_old: list[int] = []
            else:
                old_range = dict(block)
                new_range = {"start": 1, "end": 0}
                content_side = "old"
                changed_new = []
                changed_old = list(range(block["start"], block["end"] + 1)) if not range_is_empty(block) else []
            hunks.append(
                {
                    "old_range": old_range,
                    "new_range": new_range,
                    "content_side": content_side,
                    "changed_old_lines": changed_old,
                    "changed_new_lines": changed_new,
                    "provenance": "work_order",
                    "overlaps_pre_existing": False,
                }
            )
    elif change_kind == "renamed":
        total = len(head_lines)
        block = {"start": 1, "end": total}
        hunks.append(
            {
                "old_range": dict(block),
                "new_range": dict(block),
                "content_side": "new",
                "changed_old_lines": [],
                "changed_new_lines": [],
                "provenance": "work_order",
                "overlaps_pre_existing": False,
            }
        )
    else:
        if baseline_source == "commit":
            raw_hunks = diff_tracked_path(repo, commit, path)
        else:
            raw_hunks = diff_no_index(baseline_bytes or b"", head_bytes or b"", 3, tmp)

        pre_ranges: list[dict[str, int]] = []
        work_ranges: list[dict[str, int]] = []
        note = ""
        if baseline_source == "commit":
            if commit_bytes is None or baseline_bytes is None:
                note = "baseline_content_unavailable"
            else:
                pre_ranges, work_ranges, note = compute_provenance_ranges(
                    commit_bytes, baseline_bytes, head_bytes or b"", tmp
                )
        if note:
            notes.append(f"provenance_unaligned_{note}:{path}")
        for hunk in raw_hunks:
            if note:
                provenance, overlaps = "pre_existing", False
            else:
                provenance, overlaps = classify_provenance(hunk["new_range"], pre_ranges, work_ranges)
            hunks.append(
                {
                    "old_range": hunk["old_range"],
                    "new_range": hunk["new_range"],
                    "content_side": "old" if range_is_empty(hunk["new_range"]) else "new",
                    "changed_old_lines": hunk["changed_old_lines"],
                    "changed_new_lines": hunk["changed_new_lines"],
                    "provenance": provenance,
                    "overlaps_pre_existing": overlaps,
                }
            )

    entry["hunks"] = hunks
    provenances = {hunk["provenance"] for hunk in hunks}
    if provenances == {"pre_existing"}:
        entry["analyzed_as"] = "pre_existing"
    elif provenances == {"work_order"} or not hunks:
        entry["analyzed_as"] = "work_order"
    else:
        entry["analyzed_as"] = "mixed"
    return entry


def finalize_units(entries: list[dict[str, Any]]) -> None:
    """Assign the global monotonic `unit_index` (C8)."""
    unit_index = 0
    for entry in sorted(entries, key=lambda item: sort_key(item["path"])):
        entry["hunks"].sort(key=lambda hunk: (int(hunk["old_range"]["start"]), int(hunk["new_range"]["start"])))
        for hunk in entry["hunks"]:
            if hunk["provenance"] == "pre_existing":
                hunk.update(
                    {
                        "excluded": True,
                        "exclude_reason": "pre_existing_change",
                        "unit_index": None,
                        "anchor": "",
                    }
                )
                continue
            unit_index += 1
            hunk.update(
                {
                    "excluded": False,
                    "exclude_reason": "",
                    "unit_index": unit_index,
                    "anchor": f"#unit-{unit_index}",
                }
            )


def build_manifest(
    repo_path: Path,
    work_order_id: str,
    baseline_commit: str,
    baseline_digest: str,
    baseline_algorithm: str,
    baseline_worktree_dir: Path | None,
    baseline_untracked_dir: Path | None,
    tmp_dir: Path | None,
    captured_at: str,
    generated_at: str,
    strength: str,
) -> dict[str, Any]:
    repo = resolve_repo(repo_path)
    require_commit(repo, baseline_commit)

    degradations: list[str] = []
    worktree_available = bool(baseline_worktree_dir and baseline_worktree_dir.is_dir())
    untracked_available = bool(baseline_untracked_dir and baseline_untracked_dir.is_dir())
    if not worktree_available:
        degradations.append("baseline_worktree_snapshot_missing")
    if not untracked_available:
        degradations.append("baseline_untracked_snapshot_missing")

    committed = tracked_paths(repo, baseline_commit)
    tracked_changes = name_status(repo, baseline_commit)
    untracked = untracked_paths(repo)
    export_ignored = export_ignore_patterns(repo)

    if tmp_dir is not None:
        # H4/C37: the caller names the workbench tmp directory, and a workbench that has none
        # yet gets one here rather than silently falling back to the OS temp directory.
        tmp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(tmp_dir) if tmp_dir else None) as holder:
        tmp = Path(holder)
        entries: list[dict[str, Any]] = []
        notes: list[str] = []
        seen: set[str] = set()

        candidates = set(tracked_changes) | set(untracked) | set(
            snapshot_paths(baseline_untracked_dir)
        )
        for path in sorted(candidates, key=sort_key):
            in_commit = path in committed
            head_bytes = read_bytes(repo / Path(path))
            commit_bytes: bytes | None = None
            baseline_bytes: bytes | None = None
            if in_commit:
                commit_bytes = git_show_bytes(repo, baseline_commit, path)
                baseline_source = "commit"
                if worktree_available:
                    baseline_bytes = snapshot_bytes(baseline_worktree_dir, path)
                if baseline_bytes is None:
                    # No usable opening snapshot: fall back to the commit content and
                    # record the degradation instead of guessing a dirty worktree.
                    baseline_bytes = commit_bytes
            else:
                baseline_source = "untracked_snapshot"
                baseline_bytes = (
                    snapshot_bytes(baseline_untracked_dir, path) if untracked_available else None
                )
                baseline_bytes = baseline_bytes if untracked_available else None

            # Change kind and hunks come from the baseline-commit -> head diff (C29);
            # provenance then separates the pre-existing side (C37).
            origin_side = commit_bytes if in_commit else baseline_bytes
            if origin_side is None and head_bytes is None:
                continue
            if origin_side == head_bytes:
                continue
            change_kind = (
                "added" if origin_side is None else "deleted" if head_bytes is None else "modified"
            )
            entries.append(
                build_file_entry(
                    repo,
                    baseline_commit,
                    baseline_untracked_dir,
                    tmp,
                    path,
                    change_kind,
                    commit_bytes,
                    baseline_bytes if in_commit else origin_side,
                    head_bytes,
                    baseline_source,
                    worktree_available,
                    notes,
                )
            )
            seen.add(path)

        # Exact-content rename pairing (C11).
        deletions = sorted(
            (e for e in entries if e["change_kind"] == "deleted" and not e["exclude_reason"]),
            key=lambda item: sort_key(item["path"]),
        )
        additions = sorted(
            (e for e in entries if e["change_kind"] == "added" and not e["exclude_reason"]),
            key=lambda item: sort_key(item["path"]),
        )
        used: set[str] = set()
        for deletion in deletions:
            for addition in additions:
                if addition["path"] in used:
                    continue
                if addition["source_sha256"] != deletion["origin_sha256"]:
                    continue
                addition["change_kind"] = "renamed"
                addition["renamed_from"] = deletion["path"]
                addition["baseline_present"] = True
                addition["baseline_source"] = deletion["baseline_source"]
                used.add(addition["path"])
                entries.remove(deletion)
                break

        # `.gitattributes export-ignore` + credential pattern (C34 rule 2).
        if export_ignored:
            for entry in entries:
                if entry["exclude_reason"]:
                    continue
                if sensitive_path_hit(entry["path"]) and match_any_pattern(entry["path"], export_ignored):
                    entry.update({"analyzable": False, "exclude_reason": "sensitive", "hunks": []})

        finalize_units(entries)

        # Content hashes plus the redaction rule (C35).
        redacted_units: list[int] = []
        for entry in entries:
            if not entry["analyzable"]:
                continue
            for hunk in entry["hunks"]:
                lines = unit_lines(repo, baseline_commit, baseline_untracked_dir, entry, hunk)
                hunk["presentation"] = choose_presentation(hunk)
                old_rows = rendered_old_lines(
                    repo, baseline_commit, baseline_untracked_dir, entry, hunk
                )
                candidates = lines + old_rows
                if hunk["provenance"] == "work_order" and any(
                    sensitive_line_hit(line) for line in candidates
                ):
                    hunk["redacted"] = True
                    hunk["redacted_line_count"] = sum(
                        1 for line in candidates if sensitive_line_hit(line)
                    )
                    redacted_units.append(hunk["unit_index"])
                else:
                    hunk["redacted"] = False
                    hunk["redacted_line_count"] = 0
                canonical = unit_canonical_lines(lines, hunk)
                hunk["content_sha256"] = content_sha256(canonical)
                hunk["first_line"] = int(
                    (hunk["new_range"] if hunk["content_side"] == "new" else hunk["old_range"])["start"]
                )
                hunk["line_count"] = len(canonical)
                hunk["old_anchor_range"] = format_range(entry["path"], hunk["old_range"])
                hunk["new_anchor_range"] = format_range(entry["path"], hunk["new_range"])

        for entry in entries:
            entry["hunks"].sort(key=lambda hunk: hunk["unit_index"] or 0)

        units_total = sum(1 for e in entries for h in e["hunks"] if not h["excluded"])
        excluded_total = sum(1 for e in entries if not e["analyzable"])
        pre_existing_total = sum(
            1 for e in entries for h in e["hunks"] if h["provenance"] == "pre_existing"
        )
        pre_existing_files = [e["path"] for e in entries if e["analyzed_as"] != "work_order"]

        if not worktree_available:
            degradations.append("provenance_attribution_uses_baseline_commit_content")
        head_hash = digest_from_hashes([(e["path"], e["source_sha256"]) for e in entries])

        selected_strength = strength
        upgrade_reason = ""
        if strength == "minimal" and units_total > MAX_UNITS_MINIMAL:
            selected_strength = "standard"
            upgrade_reason = "units_total_exceeds_max_units_minimal"

        untracked_files = 0
        if untracked_available and baseline_untracked_dir is not None:
            untracked_files = sum(1 for item in baseline_untracked_dir.rglob("*") if item.is_file())

        manifest: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "work_order_id": work_order_id,
            "enumeration": {
                "version": ENUMERATION_VERSION,
                "algorithm": [
                    "enumerate-tracked-paths",
                    "enumerate-untracked-paths",
                    "merge-path-set",
                    "per-path-content",
                    "rename-pairing-and-unit-split",
                    "global-unit-index",
                ],
                "commands": {
                    "tracked": "git diff --no-renames --name-status -z <baseline_commit> --",
                    "untracked": "git ls-files --others --exclude-standard -z",
                    "hunks": (
                        "git diff --no-renames --no-color --diff-algorithm=myers --unified=3 "
                        "<baseline_commit> -- <path>"
                    ),
                    "untracked_hunks": (
                        "git diff --no-index --no-color --diff-algorithm=myers --unified=3 "
                        "-- <before> <after>"
                    ),
                    "provenance": (
                        "git diff --no-index --no-color --diff-algorithm=myers --unified=0 "
                        "-- <O> <B> ; git diff --no-index --no-color --diff-algorithm=myers "
                        "--unified=0 -- <B> <H>"
                    ),
                    "digest": "sha256 over sorted '<path>\\0<sha256-of-head-bytes>\\n' records",
                },
                "environment": {
                    "git_version": git_version(repo),
                    "core_autocrlf": git_config(repo, "core.autocrlf"),
                    "core_quotepath": "false (forced)",
                    "diff_renames": "disabled (--no-renames, forced)",
                },
            },
            "baseline": {
                "kind": "work-order-open-snapshot",
                "commit": baseline_commit,
                "worktree_digest": baseline_digest,
                "algorithm": baseline_algorithm,
                "captured_at": captured_at,
                "worktree_snapshot": {
                    "path": str(baseline_worktree_dir) if baseline_worktree_dir else "",
                    "available": worktree_available,
                    "algorithm": DIGEST_ALGORITHM,
                },
                "untracked_snapshot": {
                    "path": str(baseline_untracked_dir) if baseline_untracked_dir else "",
                    "files": untracked_files,
                    "algorithm": SOURCE_HASH_ALGORITHM,
                    "available": untracked_available,
                },
            },
            "head": {"kind": "worktree", "digest": head_hash, "algorithm": DIGEST_ALGORITHM},
            "generated_at": generated_at,
            "provenance_algorithm": PROVENANCE_ALGORITHM,
            "normalization": {"version": NORMALIZATION_VERSION, "algorithm": "sha256-utf8-normalized-code-text"},
            "strength": {
                "selected": selected_strength,
                "requested": strength,
                "upgraded": selected_strength != strength,
                "upgrade_reason": upgrade_reason,
            },
            "run_required": units_total > 0,
            "files": entries,
            "units_total": units_total,
            "excluded_total": excluded_total,
            "pre_existing_total": pre_existing_total,
            "pre_existing_files": pre_existing_files,
            "redacted_units": redacted_units,
            "degradations": sorted(set(degradations + notes)),
        }
    return manifest


def git_version(repo: Path) -> str:
    proc = subprocess.run(["git", "--version"], cwd=str(repo), capture_output=True)
    return proc.stdout.decode("utf-8", "replace").strip()


def git_config(repo: Path, key: str) -> str:
    proc = subprocess.run(["git", "config", "--get", key], cwd=str(repo), capture_output=True)
    if proc.returncode != 0:
        return ""
    return proc.stdout.decode("utf-8", "replace").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the xc-change-report coverage manifest.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--work-order-id", required=True)
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--baseline-digest", default="")
    parser.add_argument("--baseline-algorithm", default=DIGEST_ALGORITHM)
    parser.add_argument("--baseline-worktree-dir", default="")
    parser.add_argument("--baseline-untracked-dir", default="")
    parser.add_argument("--tmp-dir", default="")
    parser.add_argument("--captured-at", default="")
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--strength", default="standard", choices=list(STRENGTHS))
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    try:
        manifest = build_manifest(
            repo_path=Path(args.repo),
            work_order_id=args.work_order_id,
            baseline_commit=args.baseline_commit,
            baseline_digest=args.baseline_digest,
            baseline_algorithm=args.baseline_algorithm,
            baseline_worktree_dir=Path(args.baseline_worktree_dir) if args.baseline_worktree_dir else None,
            baseline_untracked_dir=Path(args.baseline_untracked_dir) if args.baseline_untracked_dir else None,
            tmp_dir=Path(args.tmp_dir) if args.tmp_dir else None,
            captured_at=args.captured_at,
            generated_at=args.generated_at,
            strength=args.strength,
        )
    except (ManifestError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(
        json.dumps(
            {
                "ok": True,
                "manifest": str(out_path.resolve()),
                "units_total": manifest["units_total"],
                "excluded_total": manifest["excluded_total"],
                "pre_existing_total": manifest["pre_existing_total"],
                "run_required": manifest["run_required"],
                "head_digest": manifest["head"]["digest"],
                "strength": manifest["strength"]["selected"],
                "strength_upgrade_reason": manifest["strength"]["upgrade_reason"],
                "degradations": manifest["degradations"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
