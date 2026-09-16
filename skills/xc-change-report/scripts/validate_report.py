#!/usr/bin/env python3
"""Validate a change report against its coverage manifest: checks V1-V16.

The validator is the execution body of the coverage proof. It recomputes what it can
(hash binding, token binding, head freshness, offline self-containment, redaction and
encoding degradation visibility) from the real worktree, the real manifest and the real
HTML, and prints a normalised receipt whose `.receipt` object is what a caller passes to
`--check-result-json`. The receipt itself is an untrusted caller self-report; the
recomputation is the proof.

Standard library only.
"""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_manifest import (  # noqa: E402
    CODE_BLOCK_CLASS,
    CODE_CONTEXT_CLASS,
    CODE_EXCLUSION_CLASSES,
    DIGEST_ALGORITHM,
    EXCLUSION_CATEGORIES,
    FIELD_NAMES,
    GATE_OUTCOME_KEY,
    IDENTIFIER_RE,
    MAX_MISLEADING,
    MAX_TEXT_NODE_CHARS,
    MAX_WRONG,
    MIN_FIELD_CHARS,
    MIN_SVG_FONT_SIZE,
    MAX_SVG_CANVAS_HEIGHT,
    MAX_SVG_CANVAS_WIDTH,
    PLACEHOLDER_TOKENS,
    RECOVERY_KEY,
    RECORDED_PATH_REASONS,
    REPORT_GATE_OUTCOMES,
    REWORK_KEY,
    SCHEMA_VERSION,
    SECTION_IDS,
    STRENGTHS,
    TABLE_CELL_CHARS,
    VERDICTS,
    DIAGRAM_TYPES,
    ENUMERATION_VERSION,
    SYMBOL_ONLY_RE,
    ManifestError,
    decode_content,
    digest_from_hashes,
    head_digest,
    normalize_code_text,
    read_bytes,
    recorded_paths,
    run_git,
    sensitive_path_hit,
    sha256_hex,
    snapshot_bytes,
    snapshot_dir,
    snapshot_paths,
    sort_key,
    split_lines,
    tracked_paths,
    tree_entries,
    unit_canonical_lines,
    unit_lines,
)
import render_diagram  # noqa: E402
from render_diagram import DiagramError  # noqa: E402

VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
URL_TEXT_RE = re.compile(r"(?:https?://|(?<![\w:/])//[A-Za-z0-9])")
# H37a bounds an exclusion interval with structural boundaries, not with a blanket
# remainder. These are the block-level containers that cannot sit inside a code block
# without ending it, so an inner descendant line-box ends the exclusion; a `pre` is the
# outermost element of the same family, so a run of stop-level tags before it is skipped.
EXCLUSION_BOUNDARY_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "body",
    "dd",
    "details",
    "dialog",
    "div",
    "dl",
    "dt",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "html",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "section",
    "summary",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}
CSS_FETCH_RE = re.compile(r"url\s*\(|@import", re.IGNORECASE)
INTEGER_ATTR_RE = re.compile(r"^(?:-?\d+)$")
DECIMAL_RE = re.compile(r"-?\d+\.\d+")
PLACEHOLDER_LEFT_RE = re.compile(r"\{\{[A-Z_]+\}\}")
CJK_RE = re.compile(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]")

# The cross-unit interface vocabulary frozen by the solution decision and stated normatively by
# `coverage-protocol.md` C4a/C4b. The strings are the interface; they are repeated here as the
# validator's own declaration of what it accepts, so that the validator does not depend on the
# builder's internal symbol names.
WORKTREE_SNAPSHOT_STATES = {
    "absent": "baseline_worktree_snapshot_missing",
    "empty": "baseline_worktree_snapshot_empty",
    "incomplete": "baseline_worktree_snapshot_incomplete",
    "complete": "",
}
UNTRACKED_SNAPSHOT_UNAVAILABLE = "baseline_untracked_snapshot_missing"

# The baseline snapshot's "not recomputable" note (C4a). It is a note, not a failure: a degraded
# capture is legal, and a validator that refused it would leave a work order with no repair route.
BASELINE_NOT_RECOMPUTABLE = "baseline_worktree_snapshot_unavailable"

# A single unit can carry a degenerate payload, and V11's failure text lists that unit's tokens.
# The list is therefore unbounded in the diff's own size; this is the declared message cap, and
# the marker keeps the truncation visible instead of hiding it.
MAX_CHECK_MESSAGE_CHARS = 400
TRUNCATION_MARKER = " ...[truncated: message capped at {limit} characters]"


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------
# HTML indexing
# --------------------------------------------------------------------------------------


class Element(dict):
    pass


class HtmlIndex(HTMLParser):
    """Structure-aware index of the report. H37b: no single large tag-matching regex."""

    def __init__(self, document: str) -> None:
        super().__init__(convert_charrefs=True)
        self.document = document
        self.line_starts = [0]
        for index, character in enumerate(document):
            if character == "\n":
                self.line_starts.append(index + 1)
        self.elements: list[Element] = []
        self._stack: list[int] = []

    def _abs_offset(self, position: tuple[int, int]) -> int:
        line, column = position
        return self.line_starts[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        start = self._abs_offset(self.getpos())
        raw = self.get_starttag_text() or ""
        element = Element(
            {
                "tag": tag,
                "attrs": {name: (value if value is not None else "") for name, value in attrs},
                "start": start,
                "start_end": start + len(raw),
                "inner_end": None,
                "end": None,
                "parent": self._stack[-1] if self._stack else None,
                "classes": [
                    item
                    for item in (dict(attrs).get("class") or "").split()
                    if item
                ],
            }
        )
        element["index"] = len(self.elements)
        self.elements.append(element)
        if tag in VOID_ELEMENTS:
            element["inner_end"] = element["start_end"]
            element["end"] = element["start_end"]
            return
        self._stack.append(element["index"])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        start = self._abs_offset(self.getpos())
        raw = self.get_starttag_text() or ""
        element = Element(
            {
                "tag": tag,
                "attrs": {name: (value if value is not None else "") for name, value in attrs},
                "start": start,
                "start_end": start + len(raw),
                "inner_end": start + len(raw),
                "end": start + len(raw),
                "parent": self._stack[-1] if self._stack else None,
                "classes": [item for item in (dict(attrs).get("class") or "").split() if item],
            }
        )
        element["index"] = len(self.elements)
        self.elements.append(element)

    def handle_endtag(self, tag: str) -> None:
        for position in range(len(self._stack) - 1, -1, -1):
            if self.elements[self._stack[position]]["tag"] != tag:
                continue
            close_at = self._abs_offset(self.getpos())
            for index in range(len(self._stack) - 1, position - 1, -1):
                element = self.elements[self._stack.pop()]
                element["inner_end"] = close_at
                match = re.compile(r"</\s*" + re.escape(tag) + r"\s*>", re.IGNORECASE).match(
                    self.document, close_at
                )
                element["end"] = close_at + (len(match.group(0)) if match else 0)
            return

    def close_open(self) -> None:
        for index in reversed(self._stack):
            element = self.elements[index]
            element["inner_end"] = len(self.document)
            element["end"] = len(self.document)
        self._stack.clear()

    def text_of(self, element: Element) -> str:
        return element_text(self.document, element)

    def by_tag(self, tag: str) -> list[Element]:
        return [element for element in self.elements if element["tag"] == tag]

    def by_class(self, class_name: str) -> list[Element]:
        return [element for element in self.elements if class_name in element["classes"]]

    def by_id(self, element_id: str) -> Element | None:
        for element in self.elements:
            if element["attrs"].get("id") == element_id:
                return element
        return None

    def ids(self) -> set[str]:
        return {element["attrs"]["id"] for element in self.elements if element["attrs"].get("id")}

    def ancestors(self, element: Element) -> Iterable[Element]:
        parent = element["parent"]
        while parent is not None:
            yield self.elements[parent]
            parent = self.elements[parent]["parent"]


TAG_STRIP_RE = re.compile(r"<[^>]*>")


def element_text(document: str, element: Element) -> str:
    raw = document[int(element["start_end"]) : int(element["inner_end"])]
    return unescape(TAG_STRIP_RE.sub("", raw))


def unescape(value: str) -> str:
    import html as html_module

    return html_module.unescape(value)


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def normalise_field(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def placeholder_hit(text: str) -> str:
    lowered = text.lower()
    for token in PLACEHOLDER_TOKENS:
        if token in {"n/a"}:
            if re.search(r"(?<![a-z0-9])n/a(?![a-z0-9])", lowered):
                return token
            continue
        if re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])", lowered):
            return token
    return ""


def has_word_content(text: str) -> bool:
    return bool(re.search(r"[0-9A-Za-z_" + "\u3400-\u9fff" + "]", text))


class Checker:
    def __init__(self) -> None:
        self.errors: list[dict[str, str]] = []

    def fail(self, check: str, message: str) -> None:
        # The cap is applied here, at the one point every check message passes through, because
        # the contract states it for every message and a per-check site would be a rule a later
        # check can forget. A message inside the cap is returned unchanged.
        self.errors.append({"id": check, "message": bounded_message(message)})

    @property
    def ok(self) -> bool:
        return not self.errors


def bounded_message(text: str, limit: int = MAX_CHECK_MESSAGE_CHARS) -> str:
    """Bound one check message, keeping its head (G-41).

    A check whose message enumerates evidence taken from the diff is unbounded in the size of
    that diff: a 240 001-character single-line unit produced a 120 144-character V11 message
    that flooded stdout and `--json-out`. The head of the message carries the check id, the unit
    number and the reason, so truncating the tail keeps the diagnostic usable and states that
    something was removed.
    """
    if len(text) <= limit:
        return text
    marker = TRUNCATION_MARKER.format(limit=limit)
    return text[: max(0, limit - len(marker))] + marker


# --------------------------------------------------------------------------------------
# V1-V16
# --------------------------------------------------------------------------------------


def _check_declared_snapshot(
    checker: Checker,
    label: str,
    snapshot: dict[str, Any],
    degradations: set[str],
    states: dict[str, str] | None,
    unavailable_degradation: str,
) -> None:
    """The A3-2 consistency tier for one declared baseline snapshot directory.

    `states` maps a declared snapshot state to the degradation string that state owes, and is
    `None` for a snapshot whose contract has no state field. An unavailable snapshot is legal —
    a failed capture degrades instead of jamming a work order — but only when the manifest says
    which degradation applies. An available snapshot must exist and must hold captured paths.
    """
    available = snapshot.get("available")
    if not isinstance(available, bool):
        checker.fail("V1", f"baseline.{label}.available must be a boolean")
        return
    expected_degradation = ""
    if states is not None:
        state = str(snapshot.get("state", "")).strip()
        if state not in states:
            checker.fail(
                "V1",
                f"baseline.{label}.state must be one of {sorted(states)}, found "
                f"{snapshot.get('state')!r}",
            )
            return
        if available != (state == "complete"):
            checker.fail(
                "V1",
                f"baseline.{label}.available is {available} while its state is {state!r}; only a "
                "complete snapshot is available",
            )
        expected_degradation = states[state]
    if not available:
        # A snapshot whose contract carries no state owes its single "missing" string.
        expected_degradation = expected_degradation or unavailable_degradation
    if expected_degradation and expected_degradation not in degradations:
        checker.fail(
            "V1",
            f"baseline.{label} is not available, so the manifest must record the degradation "
            f"{expected_degradation!r}",
        )
    if not available:
        return
    directory = Path(str(snapshot.get("path", "") or ""))
    if not directory.is_dir():
        checker.fail(
            "V1",
            f"baseline.{label}.available is true but its directory does not exist: {directory}",
        )
        return
    # The content requirement belongs to the worktree snapshot, which owes the tracked path set of
    # the baseline commit: that is exactly the state a zero-file capture must not be able to
    # claim. The untracked snapshot owes the untracked path set at open, which is legitimately
    # empty on a clean tree, so existence is its whole contract.
    if states is not None and not snapshot_paths(directory):
        checker.fail(
            "V1",
            f"baseline.{label}.available is true but its directory holds no captured path: "
            f"{directory}",
        )


def check_v1(checker: Checker, manifest: dict[str, Any], work_order_id: str) -> dict[str, int]:
    counts = {"units": 0, "excluded": 0, "pre_existing": 0}
    if int(manifest.get("schema_version", -1)) != SCHEMA_VERSION:
        checker.fail("V1", f"schema_version must be {SCHEMA_VERSION}")
    enumeration = manifest.get("enumeration", {})
    if enumeration.get("version") != ENUMERATION_VERSION:
        checker.fail("V1", f"enumeration.version must be {ENUMERATION_VERSION}")
    if manifest.get("work_order_id") != work_order_id:
        checker.fail(
            "V1",
            f"work_order_id mismatch: manifest has {manifest.get('work_order_id')!r}, "
            f"expected {work_order_id!r}",
        )
    baseline = manifest.get("baseline")
    if not isinstance(baseline, dict):
        checker.fail("V1", "baseline must be an object")
        baseline = {}
    for field in ("kind", "commit", "worktree_digest", "algorithm", "captured_at", "untracked_snapshot"):
        if field not in baseline:
            checker.fail("V1", f"baseline.{field} is required")
    if not isinstance(baseline.get("untracked_snapshot"), dict):
        checker.fail("V1", "baseline.untracked_snapshot must be an object")
    # A3-1, the content tier. Key presence is not identity: a manifest whose baseline identity is
    # empty or whose algorithm is a corrupted spelling of the C4 id used to validate at every
    # stage, so the coverage proof rested on an unproven provenance claim.
    for field in ("worktree_digest", "algorithm", "captured_at"):
        if not str(baseline.get(field, "")).strip():
            checker.fail("V1", f"baseline.{field} must be present and non-empty")
    declared_algorithm = str(baseline.get("algorithm", "")).strip()
    if declared_algorithm and declared_algorithm != DIGEST_ALGORITHM:
        checker.fail(
            "V1",
            f"baseline.algorithm must be {DIGEST_ALGORITHM!r}, found {declared_algorithm!r}",
        )
    if "worktree_snapshot" not in baseline:
        checker.fail("V1", "baseline.worktree_snapshot is required")
    elif not isinstance(baseline.get("worktree_snapshot"), dict):
        checker.fail("V1", "baseline.worktree_snapshot must be an object")
    # A3-2, the consistency tier. `available` and `degradations` are two statements about the same
    # fact, so they must agree; and a snapshot that claims to be available must really hold the
    # captured paths rather than merely exist as a directory.
    degradations = {str(item) for item in manifest.get("degradations", []) or []}
    if isinstance(baseline.get("worktree_snapshot"), dict):
        _check_declared_snapshot(
            checker,
            "worktree_snapshot",
            baseline["worktree_snapshot"],
            degradations,
            states=WORKTREE_SNAPSHOT_STATES,
            unavailable_degradation="",
        )
    if isinstance(baseline.get("untracked_snapshot"), dict):
        _check_declared_snapshot(
            checker,
            "untracked_snapshot",
            baseline["untracked_snapshot"],
            degradations,
            states=None,
            unavailable_degradation=UNTRACKED_SNAPSHOT_UNAVAILABLE,
        )
    head = manifest.get("head")
    if not isinstance(head, dict):
        checker.fail("V1", "head must be an object")
        head = {}
    for field in ("kind", "digest", "algorithm"):
        if not str(head.get(field, "")).strip():
            checker.fail("V1", f"head.{field} is required")

    files = manifest.get("files")
    if not isinstance(files, list):
        checker.fail("V1", "files must be a list")
        return counts

    expected_index = 1
    for entry in files:
        if not isinstance(entry, dict):
            checker.fail("V1", "files entries must be objects")
            continue
        if entry.get("change_kind") not in {"added", "modified", "deleted", "renamed"}:
            checker.fail("V1", f"{entry.get('path')}: unknown change_kind {entry.get('change_kind')!r}")
        if entry.get("analyzed_as") not in {"work_order", "pre_existing", "mixed"}:
            checker.fail("V1", f"{entry.get('path')}: unknown analyzed_as {entry.get('analyzed_as')!r}")
        if not isinstance(entry.get("analyzable"), bool):
            checker.fail("V1", f"{entry.get('path')}: analyzable must be a boolean")
        if not entry.get("analyzable"):
            counts["excluded"] += 1
            if entry.get("hunks"):
                checker.fail(
                    "V1",
                    f"{entry.get('path')}: excluded paths must have an empty hunks array "
                    f"(found {len(entry['hunks'])})",
                )
            if entry.get("exclude_reason") not in EXCLUSION_CATEGORIES:
                checker.fail(
                    "V1",
                    f"{entry.get('path')}: exclude_reason {entry.get('exclude_reason')!r} is not in "
                    "the closed exclusion enumeration",
                )
        hunks = entry.get("hunks")
        if not isinstance(hunks, list):
            checker.fail("V1", f"{entry.get('path')}: hunks must be a list")
            continue
        for hunk in hunks:
            if not isinstance(hunk, dict):
                checker.fail("V1", f"{entry.get('path')}: hunk entries must be objects")
                continue
            if hunk.get("provenance") not in {"work_order", "pre_existing"}:
                checker.fail("V1", f"{entry.get('path')}: unknown provenance {hunk.get('provenance')!r}")
            if hunk.get("provenance") == "pre_existing":
                counts["pre_existing"] += 1
                if hunk.get("exclude_reason") != "pre_existing_change":
                    checker.fail(
                        "V1",
                        f"{entry.get('path')}: pre-existing hunks must carry "
                        "exclude_reason=pre_existing_change",
                    )
                # C8 makes `excluded` a hunk field and C38/C15 make a pre-existing hunk an
                # excluded one. Without this field-level check a manifest whose pre-existing
                # hunk claims excluded=false passes V1 and is then reported at V10 as a
                # missing recomputation code block, which names the wrong defect.
                if hunk.get("excluded") is not True:
                    checker.fail(
                        "V1",
                        f"{entry.get('path')}: a hunk with provenance=pre_existing carries "
                        f"exclude_reason=pre_existing_change, so it must also carry "
                        f"excluded=true, found {hunk.get('excluded')!r}",
                    )
                if hunk.get("unit_index") is not None:
                    checker.fail(
                        "V1",
                        f"{entry.get('path')}: pre-existing hunks must not carry a unit_index",
                    )
                continue
            if hunk.get("excluded"):
                checker.fail("V1", f"{entry.get('path')}: a work_order hunk must not be excluded")
                continue
            counts["units"] += 1
            if hunk.get("unit_index") != expected_index:
                checker.fail(
                    "V1",
                    f"unit_index must be a global monotonic sequence starting at 1: expected "
                    f"{expected_index}, found {hunk.get('unit_index')!r} in {entry.get('path')}",
                )
            expected_index = (hunk.get("unit_index") or expected_index) + 1
            if hunk.get("anchor") != f"#unit-{hunk.get('unit_index')}":
                checker.fail(
                    "V1",
                    f"unit {hunk.get('unit_index')}: anchor must be #unit-<unit_index>, "
                    f"found {hunk.get('anchor')!r}",
                )
            if not re.fullmatch(r"[0-9a-f]{64}", str(hunk.get("content_sha256", ""))):
                checker.fail(
                    "V1", f"unit {hunk.get('unit_index')}: content_sha256 must be a sha256 hex digest"
                )

    if manifest.get("units_total") != counts["units"]:
        checker.fail(
            "V1",
            f"units_total={manifest.get('units_total')!r} does not equal the number of "
            f"analyzable hunks ({counts['units']})",
        )
    if manifest.get("excluded_total") != counts["excluded"]:
        checker.fail(
            "V1",
            f"excluded_total={manifest.get('excluded_total')!r} does not equal the number of "
            f"analyzable=false file entries ({counts['excluded']})",
        )
    if manifest.get("pre_existing_total") != counts["pre_existing"]:
        checker.fail(
            "V1",
            f"pre_existing_total={manifest.get('pre_existing_total')!r} does not equal the number "
            f"of pre_existing hunks ({counts['pre_existing']})",
        )
    return counts


def body_rows(index: HtmlIndex, table_id: str) -> list[Element]:
    """Data rows only: a <tr> inside <thead> is a header row, not a body row."""
    table = index.by_id(table_id)
    if table is None:
        return []
    rows: list[Element] = []
    for element in index.elements:
        if element["tag"] != "tr":
            continue
        ancestors = list(index.ancestors(element))
        if not any(ancestor["index"] == table["index"] for ancestor in ancestors):
            continue
        if any(ancestor["tag"] == "thead" for ancestor in ancestors):
            continue
        rows.append(element)
    return rows


def field_value(index: HtmlIndex, element: Element) -> str:
    """The analysis prose of a field block, without its heading label."""
    paragraphs = [
        item
        for item in index.elements
        if item["tag"] == "p"
        and any(ancestor["index"] == element["index"] for ancestor in index.ancestors(item))
    ]
    if paragraphs:
        return index.text_of(paragraphs[0])
    headings = [
        item
        for item in index.elements
        if item["tag"] in {"h1", "h2", "h3", "h4", "h5", "h6"}
        and any(ancestor["index"] == element["index"] for ancestor in index.ancestors(item))
    ]
    value = index.text_of(element)
    for heading in headings:
        value = value.replace(index.text_of(heading), "", 1)
    return value


def check_v2_v3(
    checker: Checker, index: HtmlIndex, manifest: dict[str, Any]
) -> tuple[int, int]:
    manifest_anchors = {
        str(hunk["anchor"]).lstrip("#")
        for entry in manifest.get("files", [])
        for hunk in entry.get("hunks", [])
        if not hunk.get("excluded") and hunk.get("anchor")
    }
    page_units = {
        element["attrs"]["id"]
        for element in index.elements
        if element["attrs"].get("id", "").startswith("unit-")
        and re.fullmatch(r"unit-\d+", element["attrs"]["id"])
    }
    covered: set[str] = set()
    for element in index.elements:
        raw = element["attrs"].get("data-covers")
        if raw:
            covered.update(item.strip().lstrip("#") for item in raw.split(",") if item.strip())

    missing = sorted(manifest_anchors - page_units, key=_anchor_key)
    if missing:
        checker.fail("V2", "missing unit sections for manifest anchors: " + ", ".join(missing))
    uncovered = sorted(manifest_anchors - covered, key=_anchor_key)
    if uncovered:
        checker.fail("V2", "unit anchors not listed in any data-covers set: " + ", ".join(uncovered))
    extra = sorted(page_units - manifest_anchors, key=_anchor_key)
    if extra:
        checker.fail("V3", "unit sections that are not in the manifest: " + ", ".join(extra))
    extra_covers = sorted(covered - manifest_anchors, key=_anchor_key)
    if extra_covers:
        checker.fail("V3", "data-covers anchors that are not in the manifest: " + ", ".join(extra_covers))
    return len(manifest_anchors) - len(missing), len(manifest_anchors)


def _anchor_key(value: str) -> tuple[int, str]:
    match = re.search(r"(\d+)$", value or "")
    return (int(match.group(1)) if match else 0, value or "")


def check_v4(checker: Checker, index: HtmlIndex, manifest: dict[str, Any]) -> None:
    for entry in manifest.get("files", []):
        for hunk in entry.get("hunks", []):
            if hunk.get("excluded"):
                continue
            unit_index = hunk["unit_index"]
            section = index.by_id(f"unit-{unit_index}")
            if section is None:
                continue
            for field in FIELD_NAMES:
                matches = [
                    element
                    for element in index.elements
                    if element["attrs"].get("data-field") == field
                    and any(ancestor["index"] == section["index"] for ancestor in index.ancestors(element))
                ]
                if not matches:
                    checker.fail("V4", f"unit {unit_index}: missing analysis field {field!r}")
                    continue
                text = matches[0]
                value = field_value(index, text).strip()
                compact = normalise_field(value)
                if not compact:
                    checker.fail("V4", f"unit {unit_index}: field {field!r} is empty")
                    continue
                if len(compact) < MIN_FIELD_CHARS:
                    checker.fail(
                        "V4",
                        f"unit {unit_index}: field {field!r} has {len(compact)} characters after "
                        f"whitespace removal, below the {MIN_FIELD_CHARS} character floor",
                    )
                    continue
                hit = placeholder_hit(value)
                if hit:
                    checker.fail(
                        "V4", f"unit {unit_index}: field {field!r} contains the placeholder {hit!r}"
                    )
                    continue
                if SYMBOL_ONLY_RE.fullmatch(compact) or not has_word_content(compact):
                    checker.fail(
                        "V4", f"unit {unit_index}: field {field!r} contains no meaningful content"
                    )
    for element in index.by_class(CODE_CONTEXT_CLASS):
        path = element["attrs"].get("data-path", "")
        lines = element["attrs"].get("data-lines", "")
        if not path:
            checker.fail("V4", "a report-code-context block has no data-path attribute")
        if not re.fullmatch(r"\d+-\d+", lines or ""):
            checker.fail(
                "V4",
                f"report-code-context block for {path or '?'} must carry a data-lines range "
                "of the form <start>-<end>",
            )


def check_v5(checker: Checker, index: HtmlIndex, manifest: dict[str, Any], manifest_bytes: bytes) -> dict[str, Any]:
    positions: list[tuple[int, str]] = []
    for section_id in SECTION_IDS:
        element = index.by_id(section_id)
        if element is None:
            checker.fail("V5", f"missing required section #{section_id}")
            continue
        positions.append((int(element["start"]), section_id))
    order = [section_id for _, section_id in sorted(positions)]
    if order != [section_id for section_id in SECTION_IDS if index.by_id(section_id) is not None]:
        checker.fail(
            "V5",
            "the nine report sections must appear in the fixed order H6-H14; found: "
            + ", ".join(order),
        )

    map_rows = body_rows(index, "change-map")
    if index.by_id("change-map") is None:
        checker.fail("V5", "the change map table (#change-map) is missing")
    elif len(map_rows) != manifest.get("units_total"):
        checker.fail(
            "V5",
            f"change map has {len(map_rows)} rows, expected units_total={manifest.get('units_total')}",
        )
    else:
        header_cells = _header_cells(index, "change-map")
        if len(header_cells) != 6:
            checker.fail("V5", f"the change map must have six columns, found {len(header_cells)}")
        for row in map_rows:
            cells = _row_cells(index, row)
            if len(cells) != 6:
                checker.fail("V5", f"change map row {row['attrs'].get('data-unit')} must have six cells")
                continue
            if not index.text_of(cells[4]).strip():
                checker.fail(
                    "V5",
                    f"change map row {row['attrs'].get('data-unit')}: the code location column is empty",
                )

    exclusion_rows = body_rows(index, "exclusion-table")
    expected_exclusions = int(manifest.get("excluded_total", 0)) + int(
        manifest.get("pre_existing_total", 0)
    )
    if index.by_id("exclusion-table") is None:
        checker.fail("V5", "the exclusion table (#exclusion-table) is missing")
    elif len(exclusion_rows) != expected_exclusions:
        checker.fail(
            "V5",
            f"exclusion table has {len(exclusion_rows)} rows, expected excluded_total + "
            f"pre_existing_total = {expected_exclusions}",
        )
    else:
        for row in exclusion_rows:
            cells = _row_cells(index, row)
            category = index.text_of(cells[1]).strip() if len(cells) > 1 else ""
            if category not in EXCLUSION_CATEGORIES:
                checker.fail("V5", f"exclusion row {category!r} does not name a valid category")

    # The rule is scoped to the page's own text, not to the source the page quotes: a
    # placeholder-shaped literal inside a code block is content the change set supplied
    # verbatim, exactly as it is for V7's URL rule, and the builder's residual guard draws the
    # same line from the other side by reading the template instead of the page. Naming the
    # surviving tokens keeps the diagnostic actionable; `Checker.fail` bounds the message.
    placeholders = unsubstituted_placeholders(index)
    if placeholders:
        checker.fail(
            "V5",
            "the report still contains an unsubstituted template placeholder: "
            + ", ".join(placeholders[:5]),
        )

    for name in ("xc-work-order-id", "xc-generated-at", "xc-manifest-sha256", "xc-report-strength"):
        found = [
            element
            for element in index.by_tag("meta")
            if element["attrs"].get("name") == name
        ]
        if not found or not found[0]["attrs"].get("content", "").strip():
            checker.fail("V5", f"the report must declare a non-empty <meta name=\"{name}\">")
    declared_hash = ""
    for element in index.by_tag("meta"):
        if element["attrs"].get("name") == "xc-manifest-sha256":
            declared_hash = element["attrs"].get("content", "")
    actual_hash = sha256_hex(manifest_bytes)
    if declared_hash and declared_hash != actual_hash:
        checker.fail(
            "V5",
            f"the report declares manifest sha256 {declared_hash} but the manifest on disk hashes "
            f"to {actual_hash}",
        )

    info = index.by_id("section-report-info")
    info_text = index.text_of(info) if info is not None else ""
    commit = str(manifest.get("baseline", {}).get("commit", ""))
    if commit and commit not in info_text:
        checker.fail("V5", "the report information section must state the baseline commit")
    rounds = body_rows(index, "round-table")
    if not rounds:
        checker.fail("V5", "the round record table (#round-table) must contain at least one row")
    else:
        first_cells = _row_cells(index, rounds[0])
        first_reason = index.text_of(first_cells[1]).strip() if len(first_cells) > 1 else ""
        if first_reason != "initial":
            checker.fail(
                "V5",
                f"the first round record must have refresh_reason=initial, found {first_reason!r}",
            )
    strength = str(manifest.get("strength", {}).get("selected", ""))
    if strength not in STRENGTHS:
        checker.fail("V5", f"manifest strength {strength!r} is not a known level")
    return {"rounds": len(rounds)}


def _header_cells(index: HtmlIndex, table_id: str) -> list[Element]:
    table = index.by_id(table_id)
    if table is None:
        return []
    return [
        element
        for element in index.elements
        if element["tag"] == "th"
        and any(ancestor["index"] == table["index"] for ancestor in index.ancestors(element))
    ]


def _row_cells(index: HtmlIndex, row: Element) -> list[Element]:
    return [
        element
        for element in index.elements
        if element["tag"] in {"td", "th"} and element["parent"] == row["index"]
    ]


def check_v6(checker: Checker, index: HtmlIndex) -> None:
    ids = index.ids()
    for element in index.by_tag("a"):
        href = element["attrs"].get("href", "")
        if href.startswith("#") and href != "#":
            if href[1:] not in ids:
                checker.fail("V6", f"internal link {href!r} points at a missing anchor")
    toc = index.by_class("report-toc")
    if not toc:
        checker.fail("V6", "the report must contain a two-level table of contents")
    else:
        links = [
            element
            for element in index.by_tag("a")
            if any(ancestor["index"] == toc[0]["index"] for ancestor in index.ancestors(element))
        ]
        if not links:
            checker.fail("V6", "the table of contents contains no entries")
        if not index.by_tag("details"):
            checker.fail("V6", "the table of contents must use the native <details> element")
    for element in index.by_class("report-unit"):
        nav = [
            child
            for child in index.elements
            if child["tag"] == "nav"
            and any(ancestor["index"] == element["index"] for ancestor in index.ancestors(child))
        ]
        if not nav:
            checker.fail(
                "V6",
                f"unit section {element['attrs'].get('id')} has no previous/next navigation",
            )


def element_has_close_tag(index: HtmlIndex, element: Element) -> bool:
    """Did the document actually close this element, or did the parser have to imply it?

    `handle_endtag` sets `end` past the closing tag while `inner_end` stops at it, so a
    parsed close tag always leaves `end > inner_end`. `close_open` gives an unclosed
    element (and every element a real close tag had to close for it) the same value for
    both, which is exactly the difference H37a needs: an element the author never closed
    must not inherit the rest of the page as its exemption.
    """
    return element["end"] is not None and int(element["end"]) > int(element["inner_end"])


def exclusion_intervals(index: HtmlIndex) -> list[tuple[int, int]]:
    """H37a: the character intervals an exclusion-class element really owns.

    An element that was never closed must not exempt the rest of the page. Its interval
    ends at its own close tag when it has one, and otherwise at the first structural
    boundary inside it: a nested exclusion-class start tag (the inner block owns its own
    interval) or the start of the first block-level container it owns. An unclosed element
    is bounded by the first block-level start tag inside it whatever that tag's position,
    because nothing about an unclosed element can be trusted to scope its own text. When
    the exclusion element is itself nested inside structural containers, those containers
    own it rather than bound it, so the walk skips a run of stop-level tags before the
    first tag that can actually hold the exclusion element.
    """
    intervals: list[tuple[int, int]] = []
    for element in index.elements:
        if not any(class_name in element["classes"] for class_name in CODE_EXCLUSION_CLASSES):
            continue
        start = int(element["start_end"])
        own_end = element["end"]
        # An element with no parsed end (a hand-built index that never closed its open
        # elements) owns nothing: refusing to exempt is the fail-closed direction, and the
        # validator always closes its index before this runs.
        if own_end is None:
            intervals.append((start, start))
            continue
        end = int(own_end)
        closed = element_has_close_tag(index, element)
        for other in index.elements:
            # `start` is the element's content start, so a boundary that begins exactly
            # there owns the content and collapses the exclusion to nothing.
            if int(other["start"]) < start:
                continue
            inner = int(other["start"])
            if inner >= end:
                continue
            if any(class_name in other["classes"] for class_name in CODE_EXCLUSION_CLASSES):
                if other is element:
                    continue
                end = inner
                break
            if other["tag"] in EXCLUSION_BOUNDARY_TAGS:
                if not closed:
                    end = inner
                    break
                parent = other["parent"]
                while (
                    parent is not None
                    and index.elements[parent]["tag"] in EXCLUSION_BOUNDARY_TAGS
                ):
                    parent = index.elements[parent]["parent"]
                if parent is not None:
                    end = inner
                    break
        intervals.append((start, min(end, len(index.document))))
    return intervals


def unsubstituted_placeholders(index: HtmlIndex) -> list[str]:
    """Placeholder-shaped tokens in the page's own text, outside the source it quotes (G-43).

    The V5 rule used to search the whole document for `{{NAME}}`, so a change set that quoted a
    placeholder-shaped literal in its source -- a message template, an f-string, a JSON sample --
    was rejected as carrying an unsubstituted placeholder even though the literal is content the
    change set supplied, not template residue. The builder's residual guard now draws the same
    line from the other side: it reads the template and never the assembled page, because a
    replacement value is not the template's business.

    The boundary is the one V7 already draws for URL text: an interval an exclusion-class element
    really owns (H37a). An element the author never closed owns only up to its first structural
    boundary, so an unclosed code block cannot exempt the rest of the page and the narrowed rule
    stays fail-closed.
    """
    exclusions = exclusion_intervals(index)
    found: list[str] = []
    for match in PLACEHOLDER_LEFT_RE.finditer(index.document):
        if any(start <= match.start() < end for start, end in exclusions):
            continue
        found.append(match.group(0))
    return found


def check_v7(checker: Checker, index: HtmlIndex) -> None:
    document = index.document
    exclusions = exclusion_intervals(index)

    def excluded(offset: int) -> bool:
        return any(start <= offset < end for start, end in exclusions)

    for match in URL_TEXT_RE.finditer(document):
        if excluded(match.start()):
            continue
        checker.fail(
            "V7",
            f"URL text outside the code-block exclusion zone at offset {match.start()}: "
            f"{document[max(0, match.start() - 20):match.start() + 30]!r}",
        )

    for element in index.elements:
        tag = element["tag"]
        attrs = element["attrs"]
        if tag == "link":
            checker.fail("V7", "<link> elements are forbidden: no external subresource is allowed")
        if tag == "script":
            script_type = attrs.get("type", "")
            if attrs.get("src"):
                checker.fail("V7", "<script src=...> is forbidden")
                continue
            if script_type != "application/json":
                checker.fail(
                    "V7",
                    "<script> predicates are mechanical: every script whose type is not "
                    "application/json fails",
                )
                continue
            element_id = attrs.get("id", "")
            extra = set(attrs) - {"type", "id"}
            if not re.fullmatch(r"diagram-spec-\d+", element_id):
                checker.fail(
                    "V7",
                    f"a JSON script block must have id diagram-spec-N, found {element_id!r}",
                )
            if extra:
                checker.fail(
                    "V7",
                    f"JSON script block {element_id!r} carries unexpected attributes: "
                    + ", ".join(sorted(extra)),
                )
        if tag in {"img", "source", "video", "audio", "track"}:
            checker.fail("V7", f"<{tag}> is a forbidden external subresource element")
        if tag == "input" and attrs.get("type", "").lower() == "image":
            checker.fail("V7", "<input type=\"image\"> is forbidden")
        if tag == "iframe":
            checker.fail("V7", "<iframe> is forbidden regardless of its src")
        if tag in {"object", "embed"}:
            checker.fail("V7", f"<{tag}> is a forbidden embedding element")
        if tag == "base":
            checker.fail("V7", "<base> is forbidden")
        if tag == "form":
            checker.fail("V7", "<form> is forbidden")
        if tag == "meta" and attrs.get("http-equiv", "").lower() == "refresh":
            checker.fail("V7", "<meta http-equiv=\"refresh\"> is forbidden")
        if "action" in attrs or "formaction" in attrs:
            checker.fail("V7", f"<{tag}> carries an action/formaction attribute, which can fetch")
        if tag in {"image", "use", "feimage"}:
            target = attrs.get("href") or attrs.get("xlink:href") or ""
            if target and not target.startswith("#"):
                checker.fail("V7", f"SVG <{tag}> may only reference the same document ({target!r})")
        if "style" in attrs and CSS_FETCH_RE.search(strip_css_comments(attrs["style"])):
            checker.fail("V7", "inline style attributes must not contain url(...) or @import")
    for element in index.by_tag("style"):
        if CSS_FETCH_RE.search(strip_css_comments(index.text_of(element))):
            checker.fail("V7", "<style> content must not contain url(...) or @import")
        if re.search(r"@font-face", index.text_of(element), re.IGNORECASE):
            checker.fail("V7", "<style> content must not declare @font-face (H34: system fonts only)")


def strip_css_comments(text: str) -> str:
    """Comments are prose; only live CSS declarations can fetch anything."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def stringify_facts(facts: dict[str, Any]) -> dict[str, str]:
    """Receipt facts are all strings: the runtime compares them to blackboard text."""
    rendered: dict[str, str] = {}
    for key, value in facts.items():
        if isinstance(value, bool):
            rendered[key] = "true" if value else "false"
        elif isinstance(value, int):
            rendered[key] = str(value)
        else:
            rendered[key] = str(value)
    return rendered


def check_v8(checker: Checker, index: HtmlIndex, golden_dir: Path | None) -> dict[str, int]:
    stats = {"diagrams": 0, "svg": 0, "table": 0}
    specs: list[dict[str, Any]] = []
    for element in index.by_tag("script"):
        if element["attrs"].get("type") != "application/json":
            continue
        raw = index.text_of(element)
        try:
            spec = json.loads(raw)
        except json.JSONDecodeError as exc:
            checker.fail("V8", f"diagram spec block {element['attrs'].get('id')} is not valid JSON: {exc}")
            continue
        if not isinstance(spec, dict):
            checker.fail("V8", f"diagram spec block {element['attrs'].get('id')} must be a JSON object")
            continue
        specs.append(spec)

    for spec in specs:
        stats["diagrams"] += 1
        diagram_id = str(spec.get("id", "?"))
        diagram_type = str(spec.get("type", ""))
        if diagram_type not in DIAGRAM_TYPES:
            checker.fail(
                "V8",
                f"diagram {diagram_id}: unsupported type {diagram_type!r}; the renderer reports "
                "unknown types instead of guessing or downgrading",
            )
            continue
        try:
            rendered = render_diagram.render_diagram(spec)
        except DiagramError as exc:
            checker.fail("V8", f"diagram {diagram_id}: {exc}")
            continue
        figure = index.by_id(diagram_id)
        if figure is None:
            checker.fail("V8", f"diagram {diagram_id}: no rendered <figure> found for this spec")
            continue
        in_page = index.document[int(figure["start"]) : int(figure["end"])]
        if in_page != rendered:
            checker.fail(
                "V8",
                f"diagram {diagram_id}: the rendered figure differs from a re-render of its spec",
            )
        if spec.get("render_mode") == "svg":
            stats["svg"] += 1
            _check_svg_geometry(checker, index, figure, spec)
            if golden_dir is not None:
                golden = golden_dir / f"{diagram_type}-golden.svg"
                if golden.is_file():
                    expected = golden.read_text(encoding="utf-8").strip()
                    actual = "\n".join(
                        index.document[int(item["start"]) : int(item["end"])]
                        for item in index.elements
                        if item["tag"] == "svg"
                        and "report-diagram-svg" in item["classes"]
                        and any(ancestor["index"] == figure["index"] for ancestor in index.ancestors(item))
                    ).strip()
                    if actual != expected:
                        checker.fail(
                            "V8",
                            f"diagram {diagram_id}: rendered SVG differs from the golden fixture "
                            f"{golden.name}",
                        )
        else:
            stats["table"] += 1
            _check_table_carrier(checker, index, figure, spec)
    return stats


def _check_svg_geometry(checker: Checker, index: HtmlIndex, figure: Element, spec: dict[str, Any]) -> None:
    diagram_id = str(spec.get("id", "?"))
    svgs = [
        element
        for element in index.elements
        if element["tag"] == "svg"
        and "report-diagram-svg" in element["classes"]
        and any(ancestor["index"] == figure["index"] for ancestor in index.ancestors(element))
    ]
    if not svgs:
        checker.fail("V8", f"diagram {diagram_id}: svg render mode produced no inline SVG")
        return
    for svg in svgs:
        width = svg["attrs"].get("width", "")
        height = svg["attrs"].get("height", "")
        if not INTEGER_ATTR_RE.fullmatch(width) or not INTEGER_ATTR_RE.fullmatch(height):
            checker.fail("V8", f"diagram {diagram_id}: svg width/height must be integers")
            continue
        if int(width) > MAX_SVG_CANVAS_WIDTH or int(height) > MAX_SVG_CANVAS_HEIGHT:
            checker.fail(
                "V8",
                f"diagram {diagram_id}: canvas {width}x{height} exceeds the "
                f"{MAX_SVG_CANVAS_WIDTH}x{MAX_SVG_CANVAS_HEIGHT} cap",
            )
        if int(width) <= 0 or int(height) <= 0:
            checker.fail("V8", f"diagram {diagram_id}: svg canvas must be positive")
        body = index.document[int(svg["start_end"]) : int(svg["inner_end"])]
        for match in re.finditer(r'font-size="([^"]+)"', body):
            value = match.group(1)
            if not INTEGER_ATTR_RE.fullmatch(value) or int(value) < MIN_SVG_FONT_SIZE:
                checker.fail(
                    "V8",
                    f"diagram {diagram_id}: font size {value!r} is below the "
                    f"{MIN_SVG_FONT_SIZE} user-unit floor",
                )
        for match in re.finditer(r'\b(?:x|y|cx|cy|r|x1|y1|x2|y2)="(-?[0-9.]+)"', body):
            if not INTEGER_ATTR_RE.fullmatch(match.group(1)):
                checker.fail(
                    "V8", f"diagram {diagram_id}: coordinates must sit on the integer grid"
                )
                break
        if DECIMAL_RE.search(re.sub(r'font-size="[^"]*"', "", body)) and 'd="' in body:
            for path_match in re.finditer(r'd="([^"]+)"', body):
                if DECIMAL_RE.search(path_match.group(1)):
                    checker.fail(
                        "V8", f"diagram {diagram_id}: path coordinates must sit on the integer grid"
                    )
                    break
        for text_element in [
            element
            for element in index.elements
            if element["tag"] == "text"
            and any(ancestor["index"] == svg["index"] for ancestor in index.ancestors(element))
        ]:
            title = [
                element
                for element in index.elements
                if element["tag"] == "title" and element["parent"] == text_element["index"]
            ]
            total_text = index.text_of(text_element)
            title_text = index.text_of(title[0]) if title else ""
            visible = total_text.replace(title_text, "", 1) if title_text else total_text
            if len(visible) > MAX_TEXT_NODE_CHARS:
                checker.fail(
                    "V8",
                    f"diagram {diagram_id}: a visible text node exceeds the "
                    f"{MAX_TEXT_NODE_CHARS} character cap",
                )
            if not visible.strip():
                checker.fail("V8", f"diagram {diagram_id}: a text node carries no visible label")
            if len(title_text) > len(visible) and title_text != visible.rstrip("\u2026"):
                checker.fail(
                    "V8",
                    f"diagram {diagram_id}: a truncated label must keep its full text in <title>",
                )
    titles = [
        element
        for element in index.elements
        if element["tag"] == "title"
        and any(ancestor["index"] == figure["index"] for ancestor in index.ancestors(element))
    ]
    descs = [
        element
        for element in index.elements
        if element["tag"] == "desc"
        and any(ancestor["index"] == figure["index"] for ancestor in index.ancestors(element))
    ]
    if not titles:
        checker.fail("V8", f"diagram {diagram_id}: every diagram needs a <title>")
    if not descs:
        checker.fail("V8", f"diagram {diagram_id}: every diagram needs a <desc>")
    summaries = [
        element
        for element in index.elements
        if "report-diagram-summary" in element["classes"]
        and any(ancestor["index"] == figure["index"] for ancestor in index.ancestors(element))
    ]
    if not summaries and not any(index.text_of(item).strip() for item in descs):
        checker.fail("V8", f"diagram {diagram_id}: every diagram needs a visible text summary")


def _check_table_carrier(checker: Checker, index: HtmlIndex, figure: Element, spec: dict[str, Any]) -> None:
    diagram_id = str(spec.get("id", "?"))
    tables = [
        element
        for element in index.elements
        if element["tag"] == "table"
        and "report-diagram-table" in element["classes"]
        and any(ancestor["index"] == figure["index"] for ancestor in index.ancestors(element))
    ]
    if not tables:
        checker.fail(
            "V8",
            f"diagram {diagram_id}: table render mode requires a structured HTML table carrier",
        )
        return
    rows = body_rows(index, tables[0]["attrs"].get("id", ""))
    if not rows:
        checker.fail("V8", f"diagram {diagram_id}: the table carrier has no data rows")
    for row in rows:
        for cell in _row_cells(index, row):
            if len(index.text_of(cell)) > TABLE_CELL_CHARS:
                checker.fail(
                    "V8",
                    f"diagram {diagram_id}: a table cell exceeds the {TABLE_CELL_CHARS} character cap",
                )
    titles = [
        element
        for element in index.elements
        if element["tag"] == "title"
        and any(ancestor["index"] == figure["index"] for ancestor in index.ancestors(element))
    ]
    descs = [
        element
        for element in index.elements
        if element["tag"] == "desc"
        and any(ancestor["index"] == figure["index"] for ancestor in index.ancestors(element))
    ]
    summaries = [
        element
        for element in index.elements
        if "report-diagram-summary" in element["classes"]
        and any(ancestor["index"] == figure["index"] for ancestor in index.ancestors(element))
    ]
    if not titles:
        checker.fail("V8", f"diagram {diagram_id}: every diagram needs a <title>")
    if not descs:
        checker.fail("V8", f"diagram {diagram_id}: every diagram needs a <desc>")
    if not summaries:
        checker.fail("V8", f"diagram {diagram_id}: a visible text summary is required")


def check_v9(checker: Checker, manifest: dict[str, Any], repo: Path) -> bool:
    paths = [entry["path"] for entry in manifest.get("files", []) if isinstance(entry, dict)]
    actual = head_digest(repo, paths)
    declared = str(manifest.get("head", {}).get("digest", ""))
    if actual != declared:
        checker.fail(
            "V9",
            f"the report is stale: the manifest declares head digest {declared} but the worktree "
            f"now hashes to {actual}. Staleness is a refresh edge, not a node failure: re-run the "
            "manifest and the skeleton for the next round.",
        )
        return False
    return True


def check_v10(checker: Checker, index: HtmlIndex, manifest: dict[str, Any]) -> int:
    bound = 0
    blocks: dict[int, list[Element]] = {}
    for element in index.by_class(CODE_BLOCK_CLASS):
        if element["tag"] != "pre":
            continue
        raw = element["attrs"].get("data-unit", "")
        if not raw.isdigit():
            checker.fail("V10", f"a {CODE_BLOCK_CLASS} block has no numeric data-unit attribute")
            continue
        blocks.setdefault(int(raw), []).append(element)
    for entry in manifest.get("files", []):
        for hunk in entry.get("hunks", []):
            if hunk.get("excluded"):
                continue
            unit_index = hunk["unit_index"]
            candidates = blocks.get(unit_index, [])
            if len(candidates) != 1:
                checker.fail(
                    "V10",
                    f"unit {unit_index}: exactly one recomputation code block is required, found "
                    f"{len(candidates)}",
                )
                continue
            inner = index.document[int(candidates[0]["start_end"]) : int(candidates[0]["inner_end"])]
            actual = sha256_hex(normalize_code_text(inner).encode("utf-8"))
            expected = str(hunk.get("content_sha256", ""))
            if actual != expected:
                checker.fail(
                    "V10",
                    f"unit {unit_index} ({entry.get('path')}) is not bound to its code: expected "
                    f"content_sha256 {expected}, recomputed {actual}",
                )
                continue
            bound += 1
    for unit_index in blocks:
        if not any(
            hunk.get("unit_index") == unit_index and not hunk.get("excluded")
            for entry in manifest.get("files", [])
            for hunk in entry.get("hunks", [])
        ):
            checker.fail("V10", f"code block data-unit={unit_index} has no matching manifest unit")
    return bound


def unit_tokens(entry: dict[str, Any], hunk: dict[str, Any], lines: list[str], changed: list[int]) -> set[str]:
    selected = [lines[number - 1] for number in changed if 0 < number <= len(lines)]
    if not selected:
        selected = lines
    text = "\n".join(selected)
    tokens = {match.group(0) for match in IDENTIFIER_RE.finditer(text) if len(match.group(0)) >= 4}
    tokens.update(re.findall(r"`([^`\n]{2,})`", text))
    path = entry["path"]
    fragments = {path, Path(path).name, Path(path).stem}
    fragments.update(part for part in re.split(r"[/\\.]", path) if len(part) >= 4)
    tokens.update(fragment for fragment in fragments if len(fragment) >= 4)
    return {token for token in tokens if token}


def check_v11(
    checker: Checker, index: HtmlIndex, manifest: dict[str, Any], repo: Path
) -> int:
    bound = 0
    commit = manifest.get("baseline", {}).get("commit", "")
    snapshot = snapshot_dir(manifest)
    for entry in manifest.get("files", []):
        for hunk in entry.get("hunks", []):
            if hunk.get("excluded"):
                continue
            unit_index = hunk["unit_index"]
            section = index.by_id(f"unit-{unit_index}")
            if section is None:
                continue
            prose = " ".join(
                field_value(index, element)
                for element in index.elements
                if element["attrs"].get("data-field") in FIELD_NAMES
                and any(ancestor["index"] == section["index"] for ancestor in index.ancestors(element))
            )
            heading = index.text_of(section)
            lines = unit_canonical_lines(unit_lines(repo, commit, snapshot, entry, hunk), hunk)
            changed = hunk["changed_old_lines"] if hunk["content_side"] == "old" else hunk["changed_new_lines"]
            tokens = unit_tokens(entry, hunk, lines, changed)
            haystack = prose
            hits = [token for token in sorted(tokens) if token in haystack]
            if not hits:
                checker.fail(
                    "V11",
                    f"unit {unit_index} ({entry.get('path')}): the analysis text shares no token "
                    f"with the unit diff. Available tokens: {', '.join(sorted(tokens)[:20])}",
                )
                continue
            bound += 1
    return bound


def check_v12(checker: Checker, flow_spec_path: Path | None) -> dict[str, Any]:
    """Gate routing consistency (O2) plus the refresh-latch pairing invariant (O1, O4)."""
    _LATCH_PAIRING_STATE.clear()
    if flow_spec_path is None or not flow_spec_path.is_file():
        return {
            "status": "not_applicable",
            "reason": "flow_spec_not_found",
            "detail": str(flow_spec_path) if flow_spec_path else "",
        }
    try:
        spec = json.loads(flow_spec_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        checker.fail("V12", f"the flow spec is not readable JSON: {exc}")
        return {"status": "failed"}

    nodes = list(_iter_nodes(spec.get("root", {})))
    by_template = {str(node.get("template_id", "")): node for node in nodes}
    gate = None
    recovery = by_template.get("report-gate-recovery-group")
    for node in nodes:
        if node.get("template_id") == "report-gate" or (
            isinstance(node.get("metadata"), dict)
            and isinstance(node["metadata"].get("gate"), dict)
            and node["metadata"]["gate"].get("outcome_key") == GATE_OUTCOME_KEY
        ):
            gate = node

    if gate is None:
        checker.fail("V12", "the flow spec declares no report-gate node with outcome_key=" + GATE_OUTCOME_KEY)
        return {"status": "failed"}
    gate_metadata = gate.get("metadata", {}).get("gate", {}) if isinstance(gate.get("metadata"), dict) else {}
    declared_raw = gate_metadata.get("outcomes", [])
    if isinstance(declared_raw, str):
        try:
            declared_raw = json.loads(declared_raw)
        except json.JSONDecodeError:
            checker.fail("V12", "metadata.gate.outcomes is not valid JSON")
            declared_raw = []
    declared = {str(item) for item in declared_raw} if isinstance(declared_raw, list) else set()

    routed: set[str] = set()
    routes_raw = gate_metadata.get("routes")
    if isinstance(routes_raw, str):
        try:
            routes_raw = json.loads(routes_raw)
        except json.JSONDecodeError:
            checker.fail("V12", "metadata.gate.routes is not valid JSON")
            routes_raw = None
    if isinstance(routes_raw, dict):
        routed.update(str(key) for key in routes_raw)
    elif isinstance(routes_raw, list):
        for item in routes_raw:
            if isinstance(item, dict) and "outcome" in item:
                routed.add(str(item["outcome"]))
    for node in nodes:
        expression = str(node.get("when", ""))
        for match in re.finditer(re.escape(GATE_OUTCOME_KEY) + r"\s*==\s*([\"']?)([\w.-]+)\1", expression):
            routed.add(match.group(2))

    if declared != set(REPORT_GATE_OUTCOMES):
        checker.fail(
            "V12",
            "metadata.gate.outcomes must be exactly the contract's four values "
            f"{sorted(REPORT_GATE_OUTCOMES)}, found {sorted(declared)}",
        )
    # The routing of the four outcomes is either declared value by value, or derived from
    # the two boolean keys the design prescribes for a runtime whose condition syntax has
    # no `||`. Whichever source the spec uses, the correspondence must hold.
    route_source = "declared" if routed else "derived-booleans"
    if routed:
        orphan = sorted(declared - routed)
        undeclared = sorted(routed - declared)
        if orphan:
            checker.fail("V12", "gate outcomes declared with no route: " + ", ".join(orphan))
        if undeclared:
            checker.fail(
                "V12",
                "gate routes that are not declared in metadata.gate.outcomes: "
                + ", ".join(undeclared),
            )
    else:
        serialized = json.dumps(spec)
        for key in (REWORK_KEY, RECOVERY_KEY):
            if key not in serialized:
                checker.fail(
                    "V12",
                    f"the spec declares no value-by-value gate routes, so it must publish the "
                    f"derived routing key {key}",
                )
    if recovery is None:
        checker.fail("V12", "the flow spec declares no report-gate-recovery-group node")
    else:
        expression = str(recovery.get("when", "")).strip()
        # The design's node table drives this group from `report.gate_recovery_required` and
        # the V12 sentence names `report.gate_rework_required`. Both are single boolean keys,
        # so both are accepted; routing on the outcome string never is.
        accepted_expressions = {f"{REWORK_KEY} == true", f"{RECOVERY_KEY} == true"}
        if expression not in accepted_expressions:
            checker.fail(
                "V12",
                "report-gate-recovery-group must be driven by a single boolean gate key "
                f"({REWORK_KEY} or {RECOVERY_KEY}) compared with true, found {expression!r}",
            )
        if GATE_OUTCOME_KEY in expression:
            checker.fail(
                "V12",
                "the rework group must not route on the gate outcome string; "
                "accepted-with-followup must not enter the rework group",
            )

    outer = by_template.get("report-pass-loop")
    if outer is None:
        checker.fail("V12", "the flow spec declares no report-pass-loop node")
    else:
        _check_loop(checker, outer, "report-pass-loop", f"{REWORK_KEY} == true")
        _check_latch_publishers(checker, spec, outer)
    inner = by_template.get("report-review-loop")
    if inner is None:
        checker.fail("V12", "the flow spec declares no report-review-loop node")
    else:
        _check_loop(checker, inner, "report-review-loop", "report.accuracy_open_issues == true")
    return {
        "status": "checked",
        "route_source": route_source,
        "latch_pairing": _LATCH_PAIRING_STATE[-1] if _LATCH_PAIRING_STATE else "undeclared",
        "declared": sorted(declared),
        "routed": sorted(routed),
    }


def _check_loop(checker: Checker, node: dict[str, Any], template_id: str, continue_when: str) -> None:
    if str(node.get("loop.max_iterations", "")).strip() != "3":
        checker.fail(
            "V12",
            f"{template_id} must declare loop.max_iterations=3, found "
            f"{node.get('loop.max_iterations')!r}",
        )
    # A bounded quality loop that cannot converge escalates; it must never kill the run.
    # `retry-failed` requires a failed executable leaf and rejects a loop, so a loop that
    # terminates `failed` is unrecoverable through the runtime and takes its whole work order
    # with it. `blocked` is the escalation terminal state the repository's other bounded
    # quality loops already declare.
    if str(node.get("loop.on_limit", "")).strip() != "blocked":
        checker.fail(
            "V12",
            f"{template_id} must declare loop.on_limit=blocked (the escalation terminal "
            f"state for a quality loop that cannot converge), found "
            f"{node.get('loop.on_limit')!r}",
        )
    actual = str(node.get("loop.continue_when", "")).strip()
    if actual != continue_when:
        checker.fail(
            "V12",
            f"{template_id} must declare loop.continue_when={continue_when!r}, found {actual!r}",
        )
    if str(node.get("executor", "")).strip() != "main":
        checker.fail("V12", f"{template_id} must be owned by the main session (executor=main)")


TERMINATING_ROUNDS = ("gate-rework", "review-loop-exit", "validate-final-stale")
# O4: one terminating path, one publisher pair. Each entry names where the round ends, the node
# that publishes `true` there, and the node that resets the key. `None` as the resetter means the
# round is deliberately ended with the key still `true`: that is how a gate rework decision carries
# control back to the next round, because `report.gate_rework_required` is the loop's continue
# condition. Resetting it in that round would end the refresh pass before the re-gate.
#
# The gate-rework path therefore publishes `true` and resets nowhere *in that round*; the round
# that follows it, judged by the gate and finalised by validate-final, owns the reset. Every
# terminating path has exactly one writer of the key. The other failure this guards is the mirror
# image: a recovery group that resets the loop's continue key satisfies "the recovery group is the
# resetter" and still ends the refresh pass before the re-gate, so the `false` a reworking round
# must not have is a declaration error, not a missing pair.
LATCH_TERMINATING_PAIRS: tuple[tuple[str, str, str, str | None, str], ...] = (
    ("gate-rework", "report-gate", "true", None, "false"),
    ("review-loop-exit", "validate-final", "true", "validate-final", "false"),
    ("validate-final-stale", "validate-final", "true", "validate-final", "false"),
)
_LATCH_PAIRING_STATE: list[str] = []


def _child_index(node: dict[str, Any], template_id: str) -> int:
    children = node.get("children", [])
    if not isinstance(children, list):
        return -1
    for position, child in enumerate(children):
        if isinstance(child, dict) and child.get("template_id") == template_id:
            return position
    return -1


def _nodes_by_template(node: Any) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in _iter_nodes(node):
        grouped.setdefault(str(item.get("template_id", "")), item)
    return grouped


def _publishes_latch(node: dict[str, Any], value: str) -> bool:
    """Does the node's own contract say it publishes `value` into the refresh key?"""
    if REWORK_KEY not in json.dumps(node, ensure_ascii=False):
        return False
    for field in ("instructions", "deliverables", "acceptance"):
        text = str(node.get(field, ""))
        for match in re.finditer(re.escape(REWORK_KEY) + r"\s*=\s*(true|false)", text):
            if match.group(1) == value:
                return True
    return False


def _parse_latch_declaration(
    checker: Checker, outer: dict[str, Any]
) -> dict[str, list[tuple[str, str]]] | None:
    metadata = outer.get("metadata", {}) if isinstance(outer.get("metadata"), dict) else {}
    if "rework_publishers" not in metadata:
        checker.fail(
            "V12",
            "the report-pass-loop node declares no metadata.rework_publishers, so the O1/O4 "
            f"pairing of {REWORK_KEY} cannot be judged at all",
        )
        return None
    raw = metadata.get("rework_publishers", "[]")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            checker.fail("V12", "metadata.rework_publishers is not valid JSON")
            return None
    if not isinstance(raw, list):
        checker.fail("V12", "metadata.rework_publishers must be a list")
        return None
    grouped: dict[str, list[tuple[str, str]]] = {name: [] for name in TERMINATING_ROUNDS}
    for item in raw:
        if not isinstance(item, dict):
            checker.fail("V12", "rework publisher entries must be objects")
            continue
        path = str(item.get("terminates_round", ""))
        node_name = str(item.get("node", "")).strip()
        value = str(item.get("publishes", "")).strip().lower()
        if value not in {"true", "false"}:
            checker.fail("V12", f"rework publisher for {path!r} must publish true or false")
            continue
        if path not in grouped:
            checker.fail(
                "V12",
                f"{path!r} is not one of the three terminating paths "
                f"{list(TERMINATING_ROUNDS)}; a fourth publisher is forbidden",
            )
            continue
        if not node_name:
            checker.fail("V12", f"rework publisher for {path!r} must name its node")
            continue
        grouped[path].append((node_name, value))
    return grouped


def _check_latch_publishers(
    checker: Checker, spec: dict[str, Any], outer: dict[str, Any]
) -> None:
    """O1/O4: one terminating path, one publisher pair, one writer per round.

    The declaration is the claim; the node set is the evidence. Each terminating path must
    be published exactly as declared, the declared node must actually own that write, and
    the round topology must give every round exactly one writer of the latch.
    """
    grouped = _parse_latch_declaration(checker, outer)
    if grouped is None:
        _LATCH_PAIRING_STATE.append("undeclared")
        return
    _LATCH_PAIRING_STATE.append("checked")
    by_template = _nodes_by_template(spec.get("root", {}))
    gate = by_template.get("report-gate")
    recovery = by_template.get("report-gate-recovery-group")
    final = by_template.get("validate-final")

    for path, true_node, true_value, false_node, false_value in LATCH_TERMINATING_PAIRS:
        entries = grouped[path]
        values = [value for _, value in entries]
        # O4: one writer per terminating round, and no node writes the key twice in one round.
        # The gate-rework path declares only the `true` it publishes: the round it terminates
        # deliberately carries no reset, because that true is the loop's continue edge.
        if false_node is None:
            if values != ["true"]:
                checker.fail(
                    "V12",
                    f"the {path!r} terminating path carries control back to the next pass, so it "
                    f"must declare exactly one {REWORK_KEY}=true write and no reset; found "
                    f"{[f'{n}={v}' for n, v in entries]}",
                )
                continue
        elif values.count("true") != 1 or values.count("false") != 1 or len(entries) != 2:
            checker.fail(
                "V12",
                f"the {path!r} terminating path must publish {REWORK_KEY} true exactly once and "
                f"reset it exactly once (O4); found {[f'{n}={v}' for n, v in entries]}",
            )
            continue
        declared = {value: name for name, value in entries}
        if declared.get("true") != true_node:
            checker.fail(
                "V12",
                f"the {path!r} terminating path must name {true_node} as the node that "
                f"publishes {REWORK_KEY}=true (O1/O4); found {declared.get('true')!r}",
            )
        if false_node is not None and declared.get("false") != false_node:
            checker.fail(
                "V12",
                f"the {path!r} terminating path must name {false_node} as the node that "
                f"publishes {REWORK_KEY}=false (O1/O4); found {declared.get('false')!r}",
            )
        publisher = by_template.get(true_node)
        if publisher is None:
            checker.fail(
                "V12",
                f"the {path!r} terminating path names {true_node!r} as the true "
                "publisher, but the spec declares no such node",
            )
        elif not _publishes_latch(publisher, "true"):
            checker.fail(
                "V12",
                f"the {path!r} terminating path declares {true_node!r} as the true "
                f"publisher, but that node's own contract never publishes {REWORK_KEY}=true",
            )
        if false_node is None:
            # A round that ends with the key still true is the re-entry edge itself. The node
            # named as the true publisher must not also reset it in that round, or the loop
            # would have nothing to continue on.
            if publisher is not None and _publishes_latch(publisher, "false"):
                checker.fail(
                    "V12",
                    f"the {path!r} terminating path carries control back to the next round, so "
                    f"{true_node!r} must not also publish {REWORK_KEY}=false; that would end the "
                    "refresh pass before the reworked report is judged",
                )
        else:
            resetter = by_template.get(false_node)
            if resetter is None:
                checker.fail(
                    "V12",
                    f"the {path!r} terminating path names {false_node!r} as the resetter, "
                    "but the spec declares no such node",
                )
            elif not _publishes_latch(resetter, "false"):
                checker.fail(
                    "V12",
                    f"the {path!r} terminating path declares {false_node!r} as the "
                    f"reset owner, but that node's own contract never publishes "
                    f"{REWORK_KEY}=false",
                )

    # The gate is one of the latch's writers, so it must be inside the round scope the loop
    # actually repeats, and the recovery arrangement must be its direct successor in that
    # same round. A gate inside the loop with the recovery group outside it spins the loop on
    # unchanged content; a gate outside the loop never judges the refreshed report.
    gate_position = _child_index(outer, "report-gate")
    recovery_position = _child_index(outer, "report-gate-recovery-group")
    if gate is None or gate_position < 0:
        checker.fail(
            "V12",
            "report-gate must be a child of report-pass-loop: a gate outside the refresh pass "
            "cannot re-open on the refreshed report and its rework decision has no round to "
            "reach",
        )
    if recovery is None or recovery_position < 0:
        checker.fail(
            "V12",
            "report-gate-recovery-group must be a child of report-pass-loop: a recovery group "
            "outside the refresh pass runs after the loop has already ended, so its rework can "
            "never be judged again",
        )
    if gate_position >= 0 and recovery_position >= 0 and recovery_position != gate_position + 1:
        checker.fail(
            "V12",
            "report-gate-recovery-group must immediately follow report-gate inside "
            "report-pass-loop, so the round that the gate terminated is the round the recovery "
            "group completes",
        )
    recovery_condition = str(recovery.get("when", "")).strip() if recovery else ""
    if recovery_condition not in {f"{REWORK_KEY} == true", f"{RECOVERY_KEY} == true"}:
        checker.fail(
            "V12",
            "report-gate-recovery-group must be driven by a single boolean gate key "
            f"({REWORK_KEY} or {RECOVERY_KEY}) compared with true, found {recovery_condition!r}",
        )
    # validate-final owns the latch on every round the gate did not terminate, so it must be
    # in the round scope as well and must be guarded off exactly when a round terminates at
    # the gate. Without the guard a gate-rework round has two writers and O4 is violated.
    final_position = _child_index(outer, "validate-final")
    if final is None or final_position < 0:
        checker.fail(
            "V12",
            "validate-final must be a child of report-pass-loop: it owns the refresh latch on "
            "every round the gate did not terminate, and it decides the refresh back-edge",
        )
    else:
        final_condition = str(final.get("when", "")).strip()
        if final_condition != f"{RECOVERY_KEY} == false":
            checker.fail(
                "V12",
                "validate-final must be guarded by "
                f"{RECOVERY_KEY} == false so it never writes the refresh latch in a round that "
                f"report-gate-recovery-group already terminated; found {final_condition!r}",
            )
        if gate_position >= 0 and recovery_position >= 0 and final_position < recovery_position:
            checker.fail(
                "V12",
                "report-gate-recovery-group must precede validate-final inside report-pass-loop, "
                "so the guarded finalizer runs after the recovery it must not race",
            )
    # O1 forbids a fourth publisher. The declaration covers the three paths; any other node
    # that claims the latch in its own contract is an undeclared writer.
    declared_writers = {str(name) for entries in grouped.values() for name, _ in entries}
    for node in _iter_nodes(spec.get("root", {})):
        template_id = str(node.get("template_id", ""))
        if template_id in declared_writers:
            continue
        if _publishes_latch(node, "true") or _publishes_latch(node, "false"):
            checker.fail(
                "V12",
                f"{template_id} publishes {REWORK_KEY} in its own contract but is not one of the "
                "declared publishers; O1 allows exactly the declared writers and no fourth one",
            )


def _iter_nodes(node: Any) -> Iterable[dict[str, Any]]:
    if not isinstance(node, dict):
        return
    yield node
    children = node.get("children", [])
    if isinstance(children, list):
        for child in children:
            yield from _iter_nodes(child)


def check_v13(checker: Checker, index: HtmlIndex, manifest: dict[str, Any], repo: Path) -> None:
    visible_text = re.sub(r"\s+", " ", unescape(index.document))
    for entry in manifest.get("files", []):
        path = str(entry.get("path", ""))
        pattern = sensitive_path_hit(path)
        if not pattern:
            continue
        if entry.get("analyzable") or entry.get("exclude_reason") != "sensitive":
            checker.fail(
                "V13",
                f"{path} matches the sensitive path pattern {pattern!r} but is not excluded with "
                "exclude_reason=sensitive",
            )
        payload = read_bytes(repo / Path(path))
        if payload is None:
            continue
        text, _ = decode_content(payload)
        for line in split_lines(text):
            stripped = line.strip()
            if len(stripped) >= 8 and stripped in visible_text:
                checker.fail(
                    "V13",
                    f"{path} is sensitive, but its content appears verbatim in the report",
                )
                break
    for entry in manifest.get("files", []):
        for hunk in entry.get("hunks", []):
            if hunk.get("excluded") or not hunk.get("redacted"):
                continue
            unit_index = hunk["unit_index"]
            section = index.by_id(f"unit-{unit_index}")
            if section is None:
                continue
            raw = index.document[int(section["start"]) : int(section["end"])]
            if "<<redacted:sha256=" not in unescape(raw):
                checker.fail(
                    "V13",
                    f"unit {unit_index}: the manifest marks this unit as redacted but the report "
                    "carries no redaction marker",
                )
    for entry in manifest.get("files", []):
        if not entry.get("encoding_unsupported"):
            continue
        if not entry.get("analyzable"):
            continue
        found = False
        for hunk in entry.get("hunks", []):
            if hunk.get("excluded"):
                continue
            section = index.by_id(f"unit-{hunk['unit_index']}")
            if section is None:
                continue
            raw = index.document[int(section["start"]) : int(section["end"])]
            if "not valid UTF-8" in raw:
                found = True
        if not found:
            checker.fail(
                "V13",
                f"{entry.get('path')}: the manifest records encoding_unsupported=true but no unit "
                "announces the decoding degradation",
            )


def check_v14(
    checker: Checker,
    manifest: dict[str, Any],
    verdicts_path: Path | None,
    accuracy_open_issues: str | None,
) -> dict[str, Any]:
    if verdicts_path is None or not verdicts_path.is_file():
        checker.fail(
            "V14",
            "change-report-verdicts.json is missing; the accuracy review node must produce it",
        )
        return {"status": "failed"}
    try:
        payload = json.loads(verdicts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        checker.fail("V14", f"change-report-verdicts.json is not valid JSON: {exc}")
        return {"status": "failed"}
    if int(payload.get("schema_version", -1)) != SCHEMA_VERSION:
        checker.fail("V14", f"verdicts schema_version must be {SCHEMA_VERSION}")
    verdicts = payload.get("verdicts")
    if not isinstance(verdicts, list):
        checker.fail("V14", "verdicts must be a list")
        return {"status": "failed"}

    expected = {
        hunk["unit_index"]
        for entry in manifest.get("files", [])
        for hunk in entry.get("hunks", [])
        if not hunk.get("excluded")
    }
    seen: dict[int, str] = {}
    wrong = 0
    misleading = 0
    for item in verdicts:
        if not isinstance(item, dict):
            checker.fail("V14", "verdict entries must be objects")
            continue
        unit_index = item.get("unit_index")
        if not isinstance(unit_index, int):
            checker.fail("V14", f"verdict entry {unit_index!r} has no integer unit_index")
            continue
        if unit_index not in expected:
            checker.fail("V14", f"verdict for unit {unit_index} is not an analyzable manifest unit")
            continue
        if unit_index in seen:
            checker.fail("V14", f"duplicate verdict for unit {unit_index}")
            continue
        verdict = item.get("verdict")
        if verdict not in VERDICTS:
            checker.fail("V14", f"unit {unit_index}: verdict {verdict!r} is outside {list(VERDICTS)}")
            continue
        if verdict in {"wrong", "misleading"} and not str(item.get("reason", "")).strip():
            checker.fail("V14", f"unit {unit_index}: a {verdict} verdict requires a non-empty reason")
        seen[unit_index] = verdict
        wrong += 1 if verdict == "wrong" else 0
        misleading += 1 if verdict == "misleading" else 0

    missing = sorted(expected - set(seen))
    if missing:
        checker.fail(
            "V14", "verdicts do not cover every analyzable unit; missing: "
            + ", ".join(str(item) for item in missing),
        )
    # MAX_WRONG is a maximum, not an exact value: the equality here rejected a run with fewer
    # wrong verdicts than the ceiling, and disagreed with `recomputed_open` two lines below,
    # which already used `>`. The two must state the same rule (G-31).
    if wrong > MAX_WRONG:
        checker.fail("V14", f"wrong verdicts: {wrong}, threshold max_wrong={MAX_WRONG}")
    if misleading > MAX_MISLEADING:
        checker.fail(
            "V14", f"misleading verdicts: {misleading}, threshold max_misleading={MAX_MISLEADING}"
        )
    recomputed_open = wrong > MAX_WRONG or misleading > MAX_MISLEADING
    if accuracy_open_issues is None:
        checker.fail(
            "V14", "the blackboard value report.accuracy_open_issues is required at this stage"
        )
    else:
        declared_open = accuracy_open_issues.strip().lower() in {"1", "true", "yes", "y"}
        if declared_open != recomputed_open:
            checker.fail(
                "V14",
                "report.accuracy_open_issues is out of step with the evidence file: blackboard says "
                f"{declared_open}, verdicts recompute to {recomputed_open}",
            )
    return {
        "status": "checked",
        "wrong": wrong,
        "misleading": misleading,
        "verdicts": len(seen),
    }


# --------------------------------------------------------------------------------------
# V15-V16: the baseline identity and the enumeration, recomputed from the repository
# --------------------------------------------------------------------------------------


def check_v15(checker: Checker, manifest: dict[str, Any], repo: Path) -> dict[str, Any]:
    """A3-3 (G-03): recompute C4's baseline digest from the recorded worktree snapshot.

    V1 can prove the baseline identity is well-formed and that the manifest tells one consistent
    story about the snapshot; only a recomputation proves the digest is the digest of those
    bytes. The construction is the package's own: `sha256(path-nul-contenthash-lf/v1)` over the
    tracked path list of `baseline.commit`, hashing each path's recorded snapshot bytes. A
    snapshot that is not available is the C4a "not recomputable" case: it is reported as a note
    and left to the recorded degradation, because a failed capture must degrade rather than jam
    the work order.
    """
    baseline = manifest.get("baseline")
    if not isinstance(baseline, dict):
        return {"status": "not_applicable", "reason": "baseline_is_not_an_object"}
    snapshot = baseline.get("worktree_snapshot")
    if not isinstance(snapshot, dict):
        return {"status": "not_applicable", "reason": "baseline_worktree_snapshot_is_not_an_object"}
    if snapshot.get("available") is not True:
        return {
            "status": "not_recomputable",
            "reason": BASELINE_NOT_RECOMPUTABLE,
            "state": str(snapshot.get("state", "")),
            "degradation": WORKTREE_SNAPSHOT_STATES.get(str(snapshot.get("state", "")).strip(), ""),
        }
    directory = Path(str(snapshot.get("path", "") or ""))
    if not directory.is_dir():
        checker.fail(
            "V15",
            f"baseline.worktree_snapshot.available is true but its directory does not exist: "
            f"{directory}",
        )
        return {"status": "failed"}
    commit = str(baseline.get("commit", ""))
    declared = str(baseline.get("worktree_digest", ""))
    try:
        tracked = sorted(tracked_paths(repo, commit), key=sort_key)
    except ManifestError as exc:
        checker.fail("V15", f"the baseline commit cannot be enumerated: {exc}")
        return {"status": "failed"}

    pairs: list[tuple[str, str]] = []
    missing: list[str] = []
    for path in tracked:
        payload = snapshot_bytes(directory, path)
        if payload is None:
            missing.append(path)
            continue
        pairs.append((path, sha256_hex(payload)))
    if missing:
        shown = ", ".join(missing[:5])
        checker.fail(
            "V15",
            f"the baseline worktree snapshot is incomplete: {len(missing)} of "
            f"{len(tracked)} tracked paths have no captured file under {directory} "
            f"({shown})",
        )
    extra = sorted(set(snapshot_paths(directory)) - set(tracked), key=sort_key)
    if extra:
        checker.fail(
            "V15",
            f"the baseline worktree snapshot holds {len(extra)} path(s) that are not tracked "
            f"at {commit}: {', '.join(extra[:5])}",
        )
    recomputed = digest_from_hashes(pairs)
    if not missing and not extra and recomputed != declared:
        checker.fail(
            "V15",
            f"the baseline worktree digest is not reproducible from {directory}: "
            f"baseline.worktree_digest is {declared!r}, the snapshot recomputes to "
            f"{recomputed!r}",
        )
    return {
        "status": "checked",
        "recomputed_digest": recomputed,
        "tracked_paths": len(tracked),
        "captured_paths": len(pairs),
    }


def check_v16(checker: Checker, manifest: dict[str, Any], repo: Path) -> dict[str, Any]:
    """A12-1 (G-30): recompute the enumeration from git, independently of the manifest.

    V5 compares the report's exclusion table with the manifest's own counters, so both sides can
    be wrong together. This check takes the sources that are not the manifest -- the
    baseline-commit diff, the index and the untracked path set -- and fails when a path a source
    reports as *changed* is absent from `files[]`. The relation is scoped to what is genuinely
    comparable: every path changed O->H, plus every index entry whose mode is neither `100644`
    nor `100755` (a gitlink or a symlink, which a byte diff of the worktree cannot see), plus
    every currently untracked path that is not already the open state's own content.

    All three scopes are scopes of *change*: C7's `files[]` is the change set, so a
    non-standard-mode index entry is only comparable when the baseline commit does not already
    record the path at that same mode and object, and an untracked path is only comparable when
    the recorded untracked snapshot does not hold those same bytes -- a file that was untracked
    when the work order opened and never changed is not a change and owes no row. A link or
    gitlink the baseline commit already holds and the work order never touches is not a change
    either, and demanding a `files[]` row for it reported a complete manifest as incomplete
    (measured: a repository whose baseline commit carries an untouched mode-`120000` entry,
    `git status --porcelain` empty).

    The third source exists because the first two are both index/commit relations: without it a
    path that reaches the enumeration as an untracked file could leave `files[]` with no row,
    no exclusion and no degradation, and the run still reported `coverage=complete` (the
    measured F1 shape). Such a path may leave `files[]` only when the manifest records it under
    one of the recorded-path reasons, which names it; a path that is named by a note about some
    other path is still a silent drop and still fails.
    """
    baseline = manifest.get("baseline")
    commit = str(baseline.get("commit", "")) if isinstance(baseline, dict) else ""
    if not commit:
        return {"status": "not_applicable", "reason": "baseline_commit_is_not_recorded"}
    diff_command = f"git diff --no-renames --name-status -z {commit} --"
    index_command = "git ls-files -s"
    untracked_command = "git ls-files --others --exclude-standard -z"
    sources: dict[str, set[str]] = {}
    try:
        diff_payload = run_git(repo, ["diff", "--no-renames", "--name-status", "-z", commit, "--"])
    except ManifestError as exc:
        checker.fail("V16", f"the baseline-commit diff cannot be recomputed: {exc}")
        return {"status": "failed"}
    fields = diff_payload.split(b"\x00")
    position = 0
    diff_paths = 0
    while position + 1 < len(fields):
        status = fields[position].decode("utf-8", "surrogateescape")
        path = fields[position + 1].decode("utf-8", "surrogateescape")
        position += 2
        if status and path:
            diff_paths += 1
            sources.setdefault(path, set()).add(diff_command)
    try:
        index_payload = run_git(repo, ["ls-files", "-s", "-z"])
    except ManifestError as exc:
        checker.fail("V16", f"the index cannot be enumerated: {exc}")
        return {"status": "failed"}
    try:
        # The baseline commit's own modes and objects: the reference the index entry's shape is
        # measured against. C15's `mode_change` is exactly this comparison, and a link is the
        # same question asked of its object id, so an entry whose mode *and* object the baseline
        # already records is not a change in either direction.
        baseline_entries = tree_entries(repo, commit)
    except ManifestError as exc:
        checker.fail("V16", f"the baseline tree cannot be enumerated: {exc}")
        return {"status": "failed"}
    index_paths = 0
    unchanged_index_entries = 0
    for record in index_payload.split(b"\x00"):
        if not record:
            continue
        meta, separator, raw_path = record.partition(b"\t")
        if not separator:
            continue
        mode = meta.split(b" ", 1)[0]
        path = raw_path.decode("utf-8", "surrogateescape")
        if not path or mode in (b"100644", b"100755"):
            continue
        recorded = baseline_entries.get(path, {})
        if (
            recorded
            and str(recorded.get("mode", "")) == mode.decode("ascii", "replace")
            and str(recorded.get("sha", "")) == meta.split(b" ")[1].decode("ascii", "replace")
        ):
            unchanged_index_entries += 1
            continue
        index_paths += 1
        sources.setdefault(path, set()).add(index_command)

    declared: set[str] = set()
    for entry in manifest.get("files", []) or []:
        if not isinstance(entry, dict):
            continue
        declared.add(str(entry.get("path", "")))
        # C11 pairs an exact-content deletion and addition into one `renamed` entry, and
        # `--no-renames` is forced on the manifest's own diff, so the deletion side of a rename
        # reaches this check as a bare `D` record while the enumeration represents it in this
        # field. Counting it is what keeps the relation comparable; a genuinely dropped path is
        # in neither place.
        renamed_from = entry.get("renamed_from")
        if renamed_from:
            declared.add(str(renamed_from))

    try:
        untracked_payload = run_git(repo, ["ls-files", "--others", "--exclude-standard", "-z"])
    except ManifestError as exc:
        checker.fail("V16", f"the untracked path set cannot be enumerated: {exc}")
        return {"status": "failed"}
    untracked_found = [
        path
        for path in (
            item.decode("utf-8", "surrogateescape")
            for item in untracked_payload.split(b"\x00")
            if item
        )
        if path
    ]
    recorded = recorded_paths(
        RECORDED_PATH_REASONS, [str(item) for item in manifest.get("degradations", []) or []]
    )
    snapshot = str(baseline.get("untracked_snapshot", {}).get("path", "") or "") if isinstance(
        baseline, dict
    ) and isinstance(baseline.get("untracked_snapshot"), dict) else ""
    untracked_snapshot = Path(snapshot) if snapshot else None
    untracked_paths = 0
    recorded_unreadable: list[str] = []
    unchanged_untracked = 0
    for path in sorted(set(untracked_found), key=sort_key):
        if path in declared:
            untracked_paths += 1
            continue
        if path in recorded:
            untracked_paths += 1
            recorded_unreadable.append(path)
            continue
        # The open state's own content: unchanged bytes between the C4a snapshot and the
        # worktree mean the path was already there when the work order opened and is not a
        # change, so it owes no row -- exactly as the enumeration decided it.
        snapshot_payload = snapshot_bytes(untracked_snapshot, path)
        if snapshot_payload is not None and snapshot_payload == read_bytes(repo / Path(path)):
            unchanged_untracked += 1
            continue
        untracked_paths += 1
        sources.setdefault(path, set()).add(untracked_command)

    missing = sorted((path for path in sources if path not in declared), key=sort_key)
    for path in missing:
        checker.fail(
            "V16",
            f"the enumeration is incomplete: path {path!r} is reported by "
            f"{' and '.join(sorted(sources[path]))} but is absent from files[] and named by no "
            "recorded-path degradation",
        )
    return {
        "status": "checked",
        "diff_paths": diff_paths,
        "index_modes": index_paths,
        # Non-standard-mode index entries the baseline commit already records byte for byte.
        # They are counted, not silently skipped, so a receipt shows how many entries the
        # change scope left out.
        "unchanged_index_modes": unchanged_index_entries,
        "untracked_paths": untracked_paths,
        "recorded_unreadable": sorted(recorded_unreadable, key=sort_key),
        "unchanged_untracked": unchanged_untracked,
        "missing": missing[:20],
    }


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------


def validate(
    report_path: Path,
    manifest_path: Path,
    repo: Path,
    work_order_id: str,
    stage: str,
    verdicts_path: Path | None,
    accuracy_open_issues: str | None,
    flow_spec_path: Path | None,
    golden_dir: Path | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    checker = Checker()
    # H26a step 7 keeps "every other space and newline", so the text sliced out of a code block
    # has to be the page's own bytes: a universal-newline read would rewrite every CRLF in the
    # document, turning the CR that ends a code line of a CRLF worktree into the LF that
    # separates the row spans and doubling that line in the recomputation.
    with report_path.open("r", encoding="utf-8", newline="") as handle:
        document = handle.read()
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    index = HtmlIndex(document)
    index.feed(document)
    index.close()
    # Every element gets a parsed end offset, so a truncated page cannot leave an element
    # with no span. H37a still bounds each exclusion to what the element really owns.
    index.close_open()

    counts = check_v1(checker, manifest, work_order_id)
    baseline_proof = check_v15(checker, manifest, repo)
    enumeration_proof = check_v16(checker, manifest, repo)
    covered, total = check_v2_v3(checker, index, manifest)
    check_v4(checker, index, manifest)
    info = check_v5(checker, index, manifest, manifest_bytes)
    check_v6(checker, index)
    check_v7(checker, index)
    diagram_stats = check_v8(checker, index, golden_dir)
    head_current = check_v9(checker, manifest, repo)
    hash_bound = check_v10(checker, index, manifest)
    token_bound = check_v11(checker, index, manifest, repo)
    gate = check_v12(checker, flow_spec_path)
    check_v13(checker, index, manifest, repo)
    if stage == "final":
        accuracy = check_v14(checker, manifest, verdicts_path, accuracy_open_issues)
    else:
        accuracy = {"status": "not_applicable", "reason": "validate-coverage runs before the review loop"}

    units_total = int(manifest.get("units_total", 0))
    coverage = "complete" if covered == total == units_total and units_total == counts["units"] else "incomplete"
    facts = {
        "units_total": units_total,
        "units_covered": covered,
        "excluded_total": int(manifest.get("excluded_total", 0)),
        "pre_existing_total": int(manifest.get("pre_existing_total", 0)),
        "hash_bound": hash_bound,
        "token_bound": token_bound,
        "coverage": coverage,
        "self_contained": not any(error["id"] == "V7" for error in checker.errors),
        "head_current": head_current,
        "strength": str(manifest.get("strength", {}).get("selected", "")),
        "rounds": int(info.get("rounds", 0)),
    }
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "check": "xc-change-report",
        "ok": checker.ok,
        "subject": str(report_path.resolve()),
        # The runtime compares a declared completion-check fact against the blackboard as an
        # exact string, so every receipt fact is emitted as text ("7", "true"). A typed fact
        # would make `--check-result-json` fail with check_fact_mismatch even though the
        # recomputation proved the coverage.
        "facts": stringify_facts(facts),
    }
    payload = {
        "ok": checker.ok,
        "stage": stage,
        "report": str(report_path.resolve()),
        "manifest": str(manifest_path.resolve()),
        "next_action": "refresh" if not head_current else "none",
        "errors": checker.errors,
        "facts": facts,
        "details": {
            "gate": gate,
            "accuracy": accuracy,
            "diagrams": diagram_stats,
            "baseline": baseline_proof,
            "enumeration": enumeration_proof,
        },
        "receipt": receipt,
    }
    return payload, receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a change report against its manifest.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--work-order-id", required=True)
    parser.add_argument("--stage", default="coverage", choices=["coverage", "final"])
    parser.add_argument("--verdicts", default="")
    parser.add_argument("--accuracy-open-issues", default=None)
    parser.add_argument("--flow-spec", default="")
    parser.add_argument("--golden-dir", default="")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args(argv)

    skill_dir = SCRIPT_DIR.parent
    flow_spec = Path(args.flow_spec) if args.flow_spec else skill_dir / "assets" / "change-report-flow.json"
    verdicts = Path(args.verdicts) if args.verdicts else None
    if verdicts is None and args.stage == "final":
        verdicts = Path(args.report).resolve().parent / "change-report-verdicts.json"
    golden_dir = Path(args.golden_dir) if args.golden_dir else None

    try:
        payload, _ = validate(
            report_path=Path(args.report),
            manifest_path=Path(args.manifest),
            repo=Path(args.repo),
            work_order_id=args.work_order_id,
            stage=args.stage,
            verdicts_path=verdicts,
            accuracy_open_issues=args.accuracy_open_issues,
            flow_spec_path=flow_spec,
            golden_dir=golden_dir,
        )
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        payload = {"ok": False, "errors": [{"id": "V0", "message": str(exc)}], "receipt": {"ok": False}}
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
