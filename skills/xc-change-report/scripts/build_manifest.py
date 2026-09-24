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

# Purpose-driven narrative layer (A16/A17). These are analysis-layer constants only: the
# purpose/theme/related-code narrative never enters the manifest, which stays pure coverage
# evidence (C6/V1/V16). A unit's `purpose` field is optional for backward compatibility with
# analysis JSON written before this layer existed.
MIN_PURPOSE_CHARS = 20
# Closed enumeration for the relation of an embedded `report-code-context` block (A17/V20).
RELATION_TYPES = ("caller", "callee", "data-structure", "contract")
# Purpose tag colour cycle: a 1-based purpose index maps to the CSS `--purpose-N` variable.
# At most six distinct purposes get a dedicated colour; beyond six the cycle repeats.
PURPOSE_COLOR_CYCLE = 6

# Analysis-depth layer (A18/A19/A20, V21/V22). Analysis-layer constants only: the change
# class, the design-dimension answers and the structured depth blocks never enter the
# manifest, which stays pure coverage evidence (C6/V1/V16). Every field below is optional, so
# analysis JSON written before this layer still loads and the V21/V22 checks stay vacuous when
# a unit declares no change class.

# A18: the closed change-taxonomy a unit may declare. The taxonomy and the design questions
# each class must answer are enumerated in references/analysis-depth.md; this tuple is the
# single machine-readable source of the legal values.
CHANGE_CLASSES = (
    "member-var",
    "constant-config",
    "data-schema",
    "global-state",
    "function",
    "signature",
    "control-flow",
    "call-dependency",
    "type-contract",
    "api-contract",
    "concurrency",
    "error-handling",
    "di-lifecycle",
    "performance",
    "refactor",
    "test-config",
    "other",
)

# A19: the canonical design-dimension keys and their human labels. A dimension is one design
# question a change should answer (the six-layer skeleton plus class-specific dimensions). The
# label is the report heading; the body language follows work_order.document_language.
DIMENSION_LABELS = {
    "role": "Role in the flow",
    "motivation": "Motivation (why, and why-not-skip)",
    "before_after": "Before vs after",
    "alternatives": "Alternatives and why rejected",
    "tradeoffs": "Trade-offs",
    "lifecycle": "Lifecycle (init / assign / read / dispose)",
    "upstream_downstream": "Upstream callers and downstream callees",
    "impact_risk": "Impact and risk",
}

# A19: the dimensions each change class MUST address. "Address" means one of the three states
# V21 enforces: an answer that clears MIN_DIMENSION_CHARS, or not_applicable=true with a
# non-empty reason. A class not listed falls back to REQUIRED_DIMENSIONS_DEFAULT. Every key
# must be in DIMENSION_LABELS. Kept small per class so the requirement stays proportional.
REQUIRED_DIMENSIONS_DEFAULT = ("role", "motivation", "impact_risk")
REQUIRED_DIMENSIONS = {
    "member-var": ("role", "motivation", "alternatives", "lifecycle", "upstream_downstream"),
    "constant-config": ("role", "motivation", "impact_risk"),
    "data-schema": ("motivation", "before_after", "impact_risk", "upstream_downstream"),
    "global-state": ("role", "alternatives", "lifecycle", "impact_risk"),
    "function": ("role", "motivation", "before_after", "upstream_downstream", "tradeoffs"),
    "signature": ("before_after", "impact_risk", "upstream_downstream"),
    "control-flow": ("role", "before_after", "impact_risk"),
    "call-dependency": ("before_after", "upstream_downstream", "impact_risk"),
    "type-contract": ("role", "before_after", "alternatives", "impact_risk"),
    "api-contract": ("before_after", "impact_risk", "upstream_downstream"),
    "concurrency": ("role", "before_after", "lifecycle", "impact_risk"),
    "error-handling": ("before_after", "impact_risk"),
    "di-lifecycle": ("role", "lifecycle", "impact_risk"),
    "performance": ("motivation", "before_after", "tradeoffs", "impact_risk"),
    "refactor": ("motivation", "before_after", "impact_risk"),
    "test-config": ("role", "motivation"),
    "other": REQUIRED_DIMENSIONS_DEFAULT,
}
# A19 thresholds. An answer must clear this many non-whitespace characters; a not-applicable
# dimension must give a reason of at least MIN_NA_REASON_CHARS, so a high-risk dimension can be
# waived only with a stated justification, never silently.
MIN_DIMENSION_CHARS = 40
MIN_NA_REASON_CHARS = 12

# A20: the closed set of structured depth-block kinds, all carried by deterministic HTML tables
# (no SVG geometry, no golden fixture). Each block binds to its unit by data-unit and is
# excluded from the V10 recomputation selection, exactly like report-code-context.
DEPTH_BLOCK_KINDS = ("before_after", "lifecycle", "call_relations")
# The change vocabulary a before_after row may carry.
DEPTH_CHANGE_VOCAB = ("added", "removed", "modified", "unchanged")
# A21/D20 prefer-diagrams advisory. These change classes are the ones for which a diagram is
# usually the best expression (a multi-step or cross-module flow, a call topology, a state
# machine, a schema or a type relationship). A unit of one of these classes that provides no
# diagram and does not mark the diagram-relevant dimensions not-applicable earns a NON-BLOCKING
# advisory, never a failure: light classes (constant-config, test-config, other) are absent
# here, and whether a diagram should really exist stays a human review judgement.
DIAGRAM_PREFERRED_CLASSES = (
    "function",
    "call-dependency",
    "control-flow",
    "concurrency",
    "data-schema",
    "type-contract",
    "api-contract",
)
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

# Exclusion categories (C15) -- a closed enumeration. Adding a category requires changing
# `references/coverage-protocol.md` first; an implementation never invents a value.
EXCLUSION_CATEGORIES = (
    "generated",
    "lockfile",
    "vendor",
    "binary",
    "minified",
    "sensitive",
    "encoding_unsupported",
    "mode_change",
    "submodule",
    "adapter_install",
    "pre_existing_change",
)

# The host-adapter and installed-Skill roots no lifecycle node owns (C13/C15/C17). `xcoding
# setup --project-root --host` and the workflow-evolution installer write into these, so a
# report states the write as a declared exclusion instead of dropping it.
ADAPTER_INSTALL_PATTERNS = (
    ".claude/*",
    "*/.claude/*",
    ".codex/*",
    "*/.codex/*",
    ".opencode/*",
    "*/.opencode/*",
    ".trae/*",
    "*/.trae/*",
    ".agents/*",
    "*/.agents/*",
)

# Index modes whose content is not the worktree file's bytes (C14a, C15).
GITLINK_MODE = "160000"
SYMLINK_MODE = "120000"

# The worktree snapshot's four states and the degradation string each unavailable state owes
# (C4b). `available` is true only for `complete`; the strings are the frozen interface.
WORKTREE_SNAPSHOT_DEGRADATIONS = {
    "absent": "baseline_worktree_snapshot_missing",
    "empty": "baseline_worktree_snapshot_empty",
    "incomplete": "baseline_worktree_snapshot_incomplete",
    "complete": "",
}
UNTRACKED_SNAPSHOT_DEGRADATION = "baseline_untracked_snapshot_missing"

# Per-path degradations: `<reason>:<path>`, the same form the C37 provenance notes use. A
# path that leaves the change set without a row is only ever allowed to leave it under one
# of these, because a degradation that names no path is indistinguishable from silence --
# and silence is the defect these notes exist to prevent.
PATH_UNREADABLE = "path_unreadable"
UNTRACKED_SNAPSHOT_PATH_LOST = "untracked_snapshot_path_lost"
MODE_PROVENANCE_UNKNOWN = "mode_provenance_unknown"
TRACKED_PATH_UNREADABLE = "tracked_path_unreadable"
UNTRACKED_PATH_UNREADABLE = "untracked_path_unreadable"
BASELINE_RECORD_UNREADABLE = "baseline_record_unreadable"
BASELINE_RECORD_UNSELECTED = "baseline_record_unselected"
# The per-path reasons the validator accepts as "the manifest recorded this path even
# though it could not enumerate it" (V16's third source).
RECORDED_PATH_REASONS = (PATH_UNREADABLE, UNTRACKED_SNAPSHOT_PATH_LOST)

OPEN_STATE_RECORD_NAME = "baseline-open-state.json"


def path_note(reason: str, path: str) -> str:
    """`<reason>:<path>` -- the package's per-path degradation form."""
    return f"{reason}:{path}"


def recorded_paths(reasons: Iterable[str], degradations: Iterable[str]) -> set[str]:
    """Every path the manifest records under one of `reasons`, parsed back from the notes."""
    markers = tuple(reason + ":" for reason in reasons)
    found: set[str] = set()
    for item in degradations:
        text = str(item)
        for marker in markers:
            if text.startswith(marker):
                found.add(text[len(marker):])
    return found


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
# Sequence-diagram SVG geometry (D22, optional sequence carrier). Participants are fixed
# columns with vertical lifelines; messages are time-ordered rows with horizontal arrows. All
# integer, so the layout is byte-deterministic and golden-fixture friendly.
SEQ_PARTICIPANT_WIDTH = 150
SEQ_PARTICIPANT_GAP = 60
SEQ_MESSAGE_GAP = 44
SEQ_HEADER_HEIGHT = 40
SEQ_TOP_MARGIN = 24
SEQ_BOTTOM_MARGIN = 24
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
    "section-purposes",
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
    """Canonical unit text: one trailing newline per kept line (H26a).

    A line's own line terminator is not part of the line, so a trailing CR is dropped and the
    line ends with the canonical LF. A worktree that stores its files with CRLF therefore
    hashes to the same `content_sha256` as the LF worktree holding the same logical text.
    Without this the hash depended on the repository's line ending while the report page
    always renders one LF per code line, so the validator could never recompute the hash of a
    CRLF worktree (V10 failed every unit).
    """
    return "".join(line.rstrip("\r") + "\n" for line in lines)


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


def decode_path(payload: bytes) -> str:
    """Decode a git path payload byte-exactly (C29 step 6, G-05).

    `surrogateescape` is the only decoding that round-trips: a path that is not valid UTF-8
    comes back as a string whose `sort_key` is the original bytes, so two distinct raw paths
    stay two distinct entries instead of collapsing onto one replacement character.
    """
    return payload.decode("utf-8", "surrogateescape")


def sort_key(path: str) -> bytes:
    """The path's own bytes, which is the ordering rule C29 step 6 fixes (G-06).

    Sorting decoded `str` is a different order: it ranks a lone surrogate above every valid
    code point, so `b"a\\xc3"` and `b"a\\xc3\\xa9"` swap. Every ordering in this module --
    the digest records, the unit index, the rename pairing and the snapshot path list -- goes
    through this one function.
    """
    return path.encode("utf-8", "surrogateescape")


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


def file_exclusion_reason(
    path: str,
    payload: bytes | None,
    text: str,
    encoding_unsupported: bool,
    shape_reason: str = "",
) -> str:
    """Deterministic file-level exclusion classification (C14, C15, C17, C34, C36).

    The classification order is the contract's: binary, sensitive, the two index-mode
    categories, adapter-install roots, generated, lockfile, vendor, minified and the
    encoding-degraded fallback. `shape_reason` carries the index-mode verdict
    (`mode_change`/`submodule`) that the caller read from `git ls-files -s`, because a shape
    is not a property of the bytes.
    """
    if payload is None:
        # A gitlink has no content at all; its shape is the whole statement.
        return shape_reason
    if looks_binary(payload):
        return "binary"
    if sensitive_path_hit(path) or sensitive_content_hits(text):
        return "sensitive"
    if shape_reason:
        return shape_reason
    if match_any_pattern(path, ADAPTER_INSTALL_PATTERNS):
        return "adapter_install"
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
    # Each `render_code_line` emits a `report-line` span that the stylesheet renders as a
    # block, so the block boundary alone places one code line per visual row. Joining the
    # spans with a literal newline as well double-spaced every code block, because the
    # enclosing `<pre>` preserves that newline and renders it as an extra blank line between
    # each pair of code lines. The spans are concatenated with no separator: the block layout
    # supplies the visible line break, and the H26a normalisation rebuilds each line from its
    # own `report-line` element (one canonical LF per element), so it never consumed the
    # inter-span newline and `content_sha256` is unchanged by dropping it.
    return "".join(render_code_line(kind, lineno, payload) for kind, lineno, payload in rows)


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
    return {decode_path(item) for item in payload.split(b"\x00") if item}


def name_status(repo: Path, commit: str) -> dict[str, str]:
    payload = run_git(repo, ["diff", "--no-renames", "--name-status", "-z", commit, "--"])
    fields = payload.split(b"\x00")
    result: dict[str, str] = {}
    index = 0
    while index + 1 < len(fields):
        raw_status = fields[index].decode("utf-8", "replace")
        path = decode_path(fields[index + 1])
        index += 2
        if not raw_status or not path:
            continue
        status = raw_status[0]
        result[path] = {"A": "added", "D": "deleted"}.get(status, "modified")
    return result


def untracked_paths(repo: Path) -> list[str]:
    payload = run_git(repo, ["ls-files", "--others", "--exclude-standard", "-z"])
    return sorted((decode_path(item) for item in payload.split(b"\x00") if item), key=sort_key)


def index_entries(repo: Path) -> dict[str, dict[str, str]]:
    """`path -> {mode, sha}` for the index, from `git ls-files -s -z` (C17).

    The index is the only source of a path's mode, and mode is what decides the two shape
    categories: a `160000` gitlink and a mode-only change are invisible to a byte diff of the
    worktree, so they are read here rather than inferred from content.
    """
    payload = run_git(repo, ["ls-files", "-s", "-z"])
    entries: dict[str, dict[str, str]] = {}
    for record in payload.split(b"\x00"):
        if not record:
            continue
        meta, separator, raw_path = record.partition(b"\t")
        if not separator or not raw_path:
            continue
        fields = meta.split(b" ")
        if len(fields) < 2:
            continue
        entries[decode_path(raw_path)] = {
            "mode": fields[0].decode("ascii", "replace"),
            "sha": fields[1].decode("ascii", "replace"),
        }
    return entries


def tree_entries(repo: Path, commit: str) -> dict[str, dict[str, str]]:
    """`path -> {mode, sha, type}` for a commit's tree, from `git ls-tree -r -z`.

    The baseline commit's mode is what a mode-only change is measured against.
    """
    payload = run_git(repo, ["ls-tree", "-r", "-z", commit])
    entries: dict[str, dict[str, str]] = {}
    for record in payload.split(b"\x00"):
        if not record:
            continue
        meta, separator, raw_path = record.partition(b"\t")
        if not separator or not raw_path:
            continue
        fields = meta.split(b" ")
        if len(fields) < 3:
            continue
        entries[decode_path(raw_path)] = {
            "mode": fields[0].decode("ascii", "replace"),
            "type": fields[1].decode("ascii", "replace"),
            "sha": fields[2].decode("ascii", "replace"),
        }
    return entries


def blob_bytes(repo: Path, object_id: str) -> bytes | None:
    """Read a blob from the object database, never through the worktree path (C14a)."""
    if not object_id:
        return None
    proc = subprocess.run(
        _git_command(["cat-file", "blob", object_id]), cwd=str(repo), capture_output=True
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


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


def read_open_state_record(
    holder: Path | None, work_order_id: str
) -> tuple[dict[str, Any] | None, list[str]]:
    """Read this work order's open-state record, with the reason when it cannot be used.

    `holder` is the record file itself, or the workbench tmp directory that contains it.
    The record carries the three facts no later step can recover -- the untracked path
    names, the index modes at open and the capture's own skips -- so a record that is
    present but unusable is a degradation that names it, never a silent fallback.
    """
    if holder is None:
        return None, []
    path = holder if holder.is_file() else holder / OPEN_STATE_RECORD_NAME
    if not path.is_file():
        return None, []
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, [path_note(BASELINE_RECORD_UNREADABLE, str(path)) + f" ({exc})"]
    if not isinstance(record, dict):
        return None, [path_note(BASELINE_RECORD_UNREADABLE, str(path))]
    selected = str(record.get("work_order_id", "") or "")
    if selected != work_order_id:
        return None, [path_note(BASELINE_RECORD_UNSELECTED, str(path))]
    return record, []


def record_untracked_paths(record: dict[str, Any] | None) -> list[str]:
    """The names that were untracked at open, as the capture recorded them (C4a)."""
    raw = (record or {}).get("untracked_paths", []) or []
    return [str(item) for item in raw if str(item)]


def record_index_modes(record: dict[str, Any] | None) -> dict[str, str]:
    """The index mode of every path at open, as the capture recorded it."""
    raw = (record or {}).get("index_modes", {}) or {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


def record_degradations(record: dict[str, Any] | None) -> list[str]:
    """The skips the capture itself recorded, which the manifest republishes."""
    raw = (record or {}).get("degradations", []) or []
    return [str(item) for item in raw if str(item)]


def record_snapshot_dirs(record: dict[str, Any] | None) -> tuple[Path | None, Path | None]:
    """The two snapshot directories the capture recorded, in record order (C4a/C4b).

    The record is the durable statement of where the opening worktree was mirrored, and it
    is the only thing that can answer that question for a caller that passes neither
    directory flag. Without them the worktree snapshot reads `absent`, every path's
    provenance alignment fails for want of the `B` side, and the whole change set is charged
    to `pre_existing` -- a materially wrong attribution that no validation stage detects, so
    the omission is resolved here rather than published.
    """
    source = record or {}
    worktree = str(source.get("worktree_snapshot", "") or "")
    untracked = str(source.get("untracked_snapshot", "") or "")
    return (Path(worktree) if worktree else None, Path(untracked) if untracked else None)


def record_captured_at(record: dict[str, Any] | None) -> str:
    """The capture timestamp the open-state record holds (C5).

    Like the two snapshot directories, ``captured_at`` is a fact the capture
    wrote once and no later read can reproduce, so a caller that passes no
    explicit ``--captured-at`` inherits it from the record instead of leaving
    the manifest baseline identity empty, which would fail coverage validation
    stage V1. An explicit argument always wins.
    """
    return str((record or {}).get("captured_at", "") or "")


def snapshot_paths(directory: Path | None) -> list[str]:
    """Every relative path captured in a baseline snapshot directory (C4a)."""
    if directory is None or not directory.is_dir():
        return []
    return sorted(
        (item.relative_to(directory).as_posix() for item in directory.rglob("*") if item.is_file()),
        key=sort_key,
    )


def worktree_snapshot_state(directory: Path | None, tracked: set[str]) -> str:
    """The worktree snapshot's C4b state: availability is decided by content (G-02).

    A directory test answers "is there a directory", not "is the baseline recomputable". The
    state is `complete` only when the captured path set equals the tracked path set of the
    baseline commit -- which is also the set C4's digest is defined over -- so a present but
    empty or partial capture is a recorded degradation instead of a silent success.
    """
    if directory is None or not directory.is_dir():
        return "absent"
    captured = set(snapshot_paths(directory))
    if not captured:
        return "empty"
    if captured == tracked:
        return "complete"
    return "incomplete"


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


def head_content_bytes(repo: Path, entry: dict[str, Any]) -> bytes | None:
    """The head side's bytes, from the object database when the path is a link (C14a).

    A `120000` entry's content is the link target text and never the bytes behind the link,
    so a path whose entry carries an index blob is read from that blob; every other path is
    read from the worktree as before.
    """
    object_id = str(entry.get("head_blob", "") or "")
    if object_id:
        return blob_bytes(repo, object_id)
    return read_bytes(repo / Path(entry["path"]))


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
        payload = head_content_bytes(repo, entry) or b""
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
        payload.extend(sort_key(path))
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
    shape_reason: str = "",
    head_blob: str = "",
    mode_origin: str = "",
    mode_head: str = "",
    mode_open: str = "",
) -> dict[str, Any]:
    """Build one `files[]` entry.

    `commit_bytes` is the baseline-commit content (O), `baseline_bytes` the work-order
    opening snapshot content (B) and `head_bytes` the current worktree content (H).
    The change kind and the hunks are taken from the O -> H diff, exactly as the
    enumeration algorithm prescribes; provenance then splits that diff into the
    pre-existing side (O -> B) and the work-order side (B -> H) (C37).

    `shape_reason` is the index-mode verdict (`mode_change`/`submodule`) the caller read from
    the index, and `head_blob` is the object the head content must be read from when the path
    is a link whose content is not the worktree file's bytes (C14a).

    `mode_origin`, `mode_head` and `mode_open` are the three modes a shape change is measured
    on: the baseline commit's mode (O), the index mode now (H) and the index mode recorded
    when the work order opened (B). No content hash can carry them, and without B the author
    of a mode-only change cannot be decided -- the bytes are identical on all three sides --
    so a shape row states all three and C37's alignment is applied to the mode itself.
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
        shape_reason=shape_reason,
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
        "head_blob": head_blob,
        "mode_origin": mode_origin,
        "mode_head": mode_head,
        "mode_open": mode_open,
        "hunks": [],
    }
    if exclusion:
        if shape_reason == "mode_change":
            # C37 applied to the mode: a flip the baseline side already shows (B == H) is not
            # this work order's, a flip the baseline side does not yet show (B == O) is, and
            # an open state that cannot say is recorded as unknown rather than charged to the
            # author on no evidence.
            if mode_open and mode_open == mode_head:
                entry["analyzed_as"] = "pre_existing"
            elif mode_open and mode_open == mode_origin:
                entry["analyzed_as"] = "work_order"
            else:
                notes.append(path_note(MODE_PROVENANCE_UNKNOWN, path))
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
        # A link's content is the link target text, which the worktree diff cannot see, so its
        # hunks come from the two recorded blobs instead of from `git diff <commit> -- <path>`.
        if baseline_source == "commit" and not head_blob:
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
    baseline_record: Path | None = None,
) -> dict[str, Any]:
    repo = resolve_repo(repo_path)
    require_commit(repo, baseline_commit)

    committed = tracked_paths(repo, baseline_commit)
    commit_modes = tree_entries(repo, baseline_commit)
    tracked_changes = name_status(repo, baseline_commit)
    untracked = untracked_paths(repo)
    index = index_entries(repo)
    export_ignored = export_ignore_patterns(repo)

    # The open state the capture recorded (C5): the untracked names, the index modes at open
    # and the capture's own skips. Every one of them is a fact no later read can reproduce,
    # so each is consumed here rather than approximated.
    record, record_notes = read_open_state_record(
        baseline_record if baseline_record is not None else tmp_dir, work_order_id
    )
    opened_untracked = record_untracked_paths(record)
    opened_modes = record_index_modes(record)
    opened_degradations = record_degradations(record)
    # The two directories are required in practice and the record already names them, so a
    # caller that passes neither gets the recorded ones instead of a silently unaligned
    # baseline. An explicit argument always wins: it is how a caller points a rebuild at a
    # snapshot the record does not know about.
    recorded_worktree_dir, recorded_untracked_dir = record_snapshot_dirs(record)
    if baseline_worktree_dir is None:
        baseline_worktree_dir = recorded_worktree_dir
    if baseline_untracked_dir is None:
        baseline_untracked_dir = recorded_untracked_dir
    # captured_at is inherited from the record on the same terms as the two
    # snapshot directories: an omitted --captured-at falls back to the value the
    # capture wrote, so a first coverage run does not fail V1 on an empty
    # baseline.captured_at. An explicit argument always wins.
    if not captured_at:
        captured_at = record_captured_at(record)

    # C4b: availability is decided by content, not by a directory test, so a present but
    # empty or partial capture degrades instead of passing as a healthy baseline.
    snapshot_state = worktree_snapshot_state(baseline_worktree_dir, committed)
    worktree_available = snapshot_state == "complete"
    untracked_available = bool(baseline_untracked_dir and baseline_untracked_dir.is_dir())
    degradations: list[str] = list(record_notes)
    if not worktree_available:
        degradations.append(WORKTREE_SNAPSHOT_DEGRADATIONS[snapshot_state])
    if not untracked_available:
        degradations.append(UNTRACKED_SNAPSHOT_DEGRADATION)

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
        # C4a: a path that was untracked at open is a candidate even when the snapshot
        # directory that held its content is gone, or a deleted one would leave the change
        # set without a row and without a name.
        candidates.update(opened_untracked)
        # C15: a `160000` gitlink is invisible to a byte diff of the worktree and its worktree
        # path is a directory, so the index entry is what makes it a candidate -- whether the
        # checkout exists or not -- and the baseline tree is what makes a removed one visible.
        candidates.update(
            path for path, entry in index.items() if str(entry.get("mode", "")) == GITLINK_MODE
        )
        candidates.update(
            path
            for path, entry in commit_modes.items()
            if str(entry.get("mode", "")) == GITLINK_MODE and path not in index
        )
        opened_untracked_set = set(opened_untracked)

        for path in sorted(candidates, key=sort_key):
            in_commit = path in committed
            index_entry = index.get(path, {})
            commit_entry = commit_modes.get(path, {})
            index_mode = str(index_entry.get("mode", ""))
            index_sha = str(index_entry.get("sha", ""))
            commit_mode = str(commit_entry.get("mode", ""))
            commit_sha = str(commit_entry.get("sha", ""))
            mode_open = opened_modes.get(path, "")
            head_blob = ""
            if index_mode == GITLINK_MODE:
                # A gitlink's recorded content is a commit id, not analysable text, and the
                # worktree path is a directory rather than bytes.
                head_bytes: bytes | None = None
            elif index_mode == SYMLINK_MODE:
                # C14a: the content is the link target text, read from the index blob. It is
                # never read through the path, because that follows the link.
                head_blob = str(index_entry.get("sha", ""))
                head_bytes = blob_bytes(repo, head_blob)
            else:
                head_bytes = read_bytes(repo / Path(path))
            commit_bytes: bytes | None = None
            baseline_bytes: bytes | None = None
            if in_commit:
                commit_bytes = git_show_bytes(repo, baseline_commit, path)
                baseline_source = "commit"
                # No usable opening snapshot for this path means B is unknown, and the C37
                # three-point alignment is impossible: it fails closed as pre-existing with
                # the reason recorded, instead of being charged to the work order.
                baseline_bytes = snapshot_bytes(baseline_worktree_dir, path)
            else:
                baseline_source = "untracked_snapshot"
                baseline_bytes = (
                    snapshot_bytes(baseline_untracked_dir, path) if untracked_available else None
                )
                baseline_bytes = baseline_bytes if untracked_available else None
            if in_commit and commit_mode == SYMLINK_MODE and not commit_bytes:
                commit_bytes = blob_bytes(repo, str(commit_entry.get("sha", "")))

            # Change kind and hunks come from the baseline-commit -> head diff (C29);
            # provenance then separates the pre-existing side (C37).
            origin_side = commit_bytes if in_commit else baseline_bytes
            shape_reason = ""
            gitlink_head = index_mode == GITLINK_MODE
            gitlink_origin = commit_mode == GITLINK_MODE
            if gitlink_head and gitlink_origin and index_sha == commit_sha:
                # C15: an unchanged pointer is not a change. A clone that never checked the
                # submodule out makes git report the missing directory as a deletion, which is
                # a fact about the worktree and not about the baseline.
                continue
            if gitlink_head or gitlink_origin:
                # The shape is the change: an added, a moved or a removed gitlink is recorded
                # whether or not its worktree path exists.
                shape_reason = "submodule"
            elif (
                in_commit
                and index_mode
                and commit_mode
                and index_mode != commit_mode
                and origin_side == head_bytes
            ):
                # C15: the index mode changed while the bytes did not. The equal-bytes
                # shortcut must not drop it, because the change is the shape.
                shape_reason = "mode_change"
            if not shape_reason:
                if origin_side is None and head_bytes is None:
                    # Neither side holds a readable path. The two measured shapes are a path
                    # git spells with a replacement character and cannot open, and a path that
                    # was untracked at open whose snapshot directory is gone. Both are
                    # recorded by name: an unreadable path that leaves the change set without
                    # a row and without a note is invisible to the whole proof.
                    if path in opened_untracked_set:
                        notes.append(path_note(UNTRACKED_SNAPSHOT_PATH_LOST, path))
                    else:
                        notes.append(path_note(PATH_UNREADABLE, path))
                    continue
                if origin_side == head_bytes:
                    continue
            if shape_reason == "submodule":
                # Presence decides the kind for a shape whose content is never readable: the
                # gitlink is in the baseline tree, in the index, in both, or in one of them.
                # A worktree diff cannot see a gitlink at all, so git's own status is not
                # better evidence here and is not consulted.
                if gitlink_origin and gitlink_head:
                    change_kind = "modified"
                elif gitlink_head:
                    change_kind = "added"
                else:
                    change_kind = "deleted"
            else:
                change_kind = (
                    "added" if origin_side is None else "deleted" if head_bytes is None else "modified"
                )
                if shape_reason and tracked_changes.get(path):
                    # A mode-only change has equal bytes on both sides, so git's own status for
                    # the path is what states the kind.
                    change_kind = tracked_changes[path]
            entry = build_file_entry(
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
                shape_reason=shape_reason,
                head_blob=head_blob,
                mode_origin=commit_mode,
                mode_head=index_mode,
                mode_open=mode_open,
            )
            if shape_reason == "submodule":
                # Presence is structural for a gitlink; its content is a commit id and never
                # the bytes of a file, so the two presence flags follow the two index/tree
                # entries rather than the two byte reads.
                entry["baseline_present"] = gitlink_origin
                entry["head_present"] = gitlink_head
            entries.append(entry)
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
        # C37.4: the overlapped region is charged to the work order by the fixed conservative
        # rule, so it is counted rather than excluded -- the counter is where a reader sees the
        # size of the region the rule attributes to this work order.
        overlapped_pre_existing_total = sum(
            1
            for e in entries
            for h in e["hunks"]
            if h["provenance"] == "work_order" and h["overlaps_pre_existing"]
        )
        pre_existing_files = [e["path"] for e in entries if e["analyzed_as"] != "work_order"]

        # No aggregate marker is added here: an unavailable snapshot already records its own
        # C4b state string above, and every path whose B side was unavailable records the
        # per-path `provenance_unaligned_baseline_content_unavailable` note.
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
                    "state": snapshot_state,
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
            "overlapped_pre_existing_total": overlapped_pre_existing_total,
            "pre_existing_files": pre_existing_files,
            "redacted_units": redacted_units,
            # The capture's own skips travel with the manifest: a tracked path the capture
            # could not mirror is why the snapshot state degrades, and the report's
            # degradation list is where a reader sees which path it was.
            "degradations": sorted(set(degradations + notes + opened_degradations)),
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
    parser.add_argument(
        "--baseline-worktree-dir",
        default="",
        help=(
            "The opening worktree snapshot. Defaults to the path this work order's open-state "
            "record holds, so a caller that omits it still gets an aligned baseline instead of "
            "a change set charged to pre_existing."
        ),
    )
    parser.add_argument(
        "--baseline-untracked-dir",
        default="",
        help=(
            "The opening untracked-file snapshot. Defaults to the path this work order's "
            "open-state record holds."
        ),
    )
    parser.add_argument("--tmp-dir", default="")
    parser.add_argument(
        "--baseline-record",
        default="",
        help=(
            "This work order's open-state record; defaults to "
            "<tmp-dir>/baseline-open-state.json, which is where the capture tool writes it."
        ),
    )
    parser.add_argument(
        "--captured-at",
        default="",
        help=(
            "The baseline capture timestamp. Defaults to the captured_at this "
            "work order's open-state record holds, so an omitted flag is not "
            "fatal for a work order whose record is present."
        ),
    )
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
            baseline_record=Path(args.baseline_record) if args.baseline_record else None,
        )
    except (ManifestError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # `ensure_ascii=True` is what makes a path that is not valid UTF-8 serialisable: the
    # surrogate-escaped decoding of such a path has no UTF-8 encoding, so an ASCII-only
    # document with `\\udcXX` escapes is the form that survives the round trip (G-05).
    out_path.write_bytes((json.dumps(manifest, ensure_ascii=True, indent=2) + "\n").encode("utf-8"))
    print(
        json.dumps(
            {
                "ok": True,
                "manifest": str(out_path.resolve()),
                "units_total": manifest["units_total"],
                "excluded_total": manifest["excluded_total"],
                "pre_existing_total": manifest["pre_existing_total"],
                "overlapped_pre_existing_total": manifest["overlapped_pre_existing_total"],
                "run_required": manifest["run_required"],
                "head_digest": manifest["head"]["digest"],
                "strength": manifest["strength"]["selected"],
                "strength_upgrade_reason": manifest["strength"]["upgrade_reason"],
                "worktree_snapshot_state": manifest["baseline"]["worktree_snapshot"]["state"],
                "degradations": manifest["degradations"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
