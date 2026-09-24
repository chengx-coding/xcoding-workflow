#!/usr/bin/env python3
"""Build the single-file `change-report.html` from a manifest, the template and analysis text.

Division of labour (contract: "scripts build the skeleton, the model writes the
explanation"): every mechanical part of the page -- section order, table rows, anchors,
code blocks, rendering of diagram specs -- is produced here; only the prose comes from
the analysis JSON. The builder verifies its own code blocks by normalising them again
and comparing the result with the manifest content hash, so a mismatched block can never
reach the report.

Standard library only.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_manifest import (  # noqa: E402
    ANCHOR_CLASS,
    CHANGE_CLASSES,
    CODE_BLOCK_CLASS,
    CODE_CONTEXT_CLASS,
    DEPTH_BLOCK_KINDS,
    DEPTH_CHANGE_VOCAB,
    DIMENSION_LABELS,
    FIELD_NAMES,
    MIN_DIMENSION_CHARS,
    MIN_NA_REASON_CHARS,
    REQUIRED_DIMENSIONS,
    REQUIRED_DIMENSIONS_DEFAULT,
    MIN_PURPOSE_CHARS,
    PURPOSE_COLOR_CYCLE,
    RELATION_TYPES,
    SCHEMA_VERSION,
    SECTION_IDS,
    STRENGTHS,
    diff_no_index,
    diff_tracked_path,
    decode_content,
    file_slug,
    git_show_bytes,
    normalize_code_text,
    read_bytes,
    redact_line,
    render_code_rows,
    sha256_hex,
    snapshot_bytes,
    snapshot_dir,
    sort_key,
    split_lines,
    unit_canonical_lines,
    unit_lines,
)
from highlight_code import detect_language, highlight  # noqa: E402
import render_diagram  # noqa: E402
from render_diagram import DiagramError  # noqa: E402

# H4/C37: the workbench tmp directory the current render was asked to use. `None` means
# the caller supplied none, and only then does the process fall back to the OS temp dir.
_TMP_DIR: Path | None = None

DEFAULT_SECTION_TITLES = {
    "overview": "Overview",
    "purposes": "Purposes and themes",
    "change-map": "Change map",
    "process-position": "Position in the wider flow",
    "units": "Unit-by-unit analysis",
    "related-code": "Related unchanged code",
    "diagrams": "Diagrams",
    "verification": "Verification and evidence",
    "glossary": "Glossary",
    "report-info": "Report information",
}

FIELD_LABELS = {
    "what": "What it does",
    "why": "Why it exists",
    "design": "Design intent",
    "tradeoffs": "Trade-offs",
    "flow-position": "Position in the flow",
    "alternatives": "Alternatives considered",
    "business-process": "Business process",
    "data-and-control": "Data flow and control",
}

# Presentation split of the eight A1-A8 fields (content is unchanged; every field is still
# rendered and still validated by V4). Primary fields stay open; secondary fields fold into a
# native <details>. Their union and order match FIELD_NAMES.
PRIMARY_FIELDS = ("what", "why", "design", "flow-position")
SECONDARY_FIELDS = ("tradeoffs", "alternatives", "business-process", "data-and-control")

PLACEHOLDERS = (
    "DOCUMENT_LANGUAGE",
    "REPORT_TITLE",
    "REPORT_SUBTITLE",
    "WORK_ORDER_ID",
    "GENERATED_AT",
    "MANIFEST_SHA256",
    "STRENGTH",
    "STYLE",
    "TOC",
    "SECTION_OVERVIEW_TITLE",
    "SECTION_PURPOSES_TITLE",
    "SECTION_CHANGE_MAP_TITLE",
    "META_BADGES",
    "PURPOSES",
    "QUICK_INDEX",
    "SECTION_PROCESS_POSITION_TITLE",
    "SECTION_UNITS_TITLE",
    "SECTION_RELATED_CODE_TITLE",
    "SECTION_DIAGRAMS_TITLE",
    "SECTION_VERIFICATION_TITLE",
    "SECTION_GLOSSARY_TITLE",
    "SECTION_REPORT_INFO_TITLE",
    "OVERVIEW",
    "CHANGE_MAP",
    "EXCLUSION_TABLE",
    "PROCESS_POSITION",
    "UNITS",
    "RELATED_CODE",
    "DIAGRAMS",
    "VERIFICATION",
    "GLOSSARY",
    "REPORT_INFO",
    "FOOTER_NOTE",
)

# The declared placeholder set, as a lookup for the residual check below (G-43). The template
# is the only place a placeholder may live; every `{{NAME}}` it carries must be one of these.
PLACEHOLDER_SET = frozenset(PLACEHOLDERS)
# A placeholder-shaped token. The inner text is matched loosely (not as `[A-Z_]+`) so that a
# mistyped or differently-cased declared name is still recognised as a token instead of being
# mistaken for literal content.
TEMPLATE_TOKEN_RE = re.compile(r"\{\{([^{}]*)\}\}")


class SkeletonError(RuntimeError):
    pass


def template_residue(template_text: str) -> list[str]:
    """Placeholder-shaped tokens in the *template* that substitution cannot resolve (G-43).

    The residual check runs over the template, never over the assembled page. A change set
    may quote source that contains a literal brace pair -- a Python f-string, a JSON literal,
    a JavaScript or CSS block -- and the builder copies that source into the page verbatim;
    those braces are quoted content, not an unresolved placeholder, so scanning the page
    rejected whole change sets that have nothing wrong with them.

    A token the declared `PLACEHOLDERS` set does not cover is treated as residue: substitution
    replaces exactly the declared names, so such a token survives into the page and is a
    genuine unresolved placeholder. A stray `{{` or `}}` that is not part of a token is
    residue for the same reason.
    """
    residue: list[str] = []
    for match in TEMPLATE_TOKEN_RE.finditer(template_text):
        if match.group(1).strip() not in PLACEHOLDER_SET:
            residue.append(match.group(0))
    remainder = TEMPLATE_TOKEN_RE.sub("", template_text)
    if "{{" in remainder or "}}" in remainder:
        residue.append("unbalanced '{{' or '}}' outside a placeholder token")
    return residue


# A git path that is not valid UTF-8 decodes to lone surrogates `U+DC80`-`U+DCFF` -- one per
# raw byte, which is what `build_manifest.decode_path` produces so that the path stays
# lossless. Such a character has no UTF-8 encoding at all, so a page that carried it could
# neither be written nor read back as UTF-8. Each one is rendered as the escape the manifest
# already uses for the same bytes (its writer is pinned to `ensure_ascii=True`), so the two
# artefacts spell an unencodable path identically.
_SURROGATE_RENDERING = {code: f"\\u{code:04x}" for code in range(0xDC80, 0xDD00)}


def page_text(page: str) -> str:
    """Make the assembled page encodable as UTF-8, changing nothing else (F2).

    Every character that has a UTF-8 encoding is passed through untouched; only a lone
    surrogate, which cannot be encoded, is replaced by its ASCII escape.
    """
    return page.translate(_SURROGATE_RENDERING)


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def paragraph(text: str) -> str:
    stripped = str(text).strip()
    return f"<p>{escape(stripped)}</p>" if stripped else "<p></p>"


def _code_location(hunk: dict[str, Any]) -> str:
    return hunk["old_anchor_range"] if hunk["content_side"] == "old" else hunk["new_anchor_range"]


def _find_diff_hunk(repo: Path, manifest: dict[str, Any], entry: dict[str, Any], hunk: dict[str, Any]) -> list[tuple[str, int, str]]:
    """Recompute the unified-diff rows for a unit whose presentation is `diff`."""
    commit = manifest["baseline"]["commit"]
    if entry.get("change_kind") == "added":
        # A whole-file addition has no baseline hunk to align with; the unified-diff
        # presentation of an added window is a header plus one `+` row per line.
        from build_manifest import range_length

        return ["add"] * range_length(hunk["new_range"])
    if entry.get("baseline_source") == "commit":
        hunks = diff_tracked_path(repo, commit, entry["path"])
    else:
        snapshot = snapshot_dir(manifest)
        before = snapshot_bytes(snapshot, entry["path"]) or b""
        after = read_bytes(repo / Path(entry["path"])) or b""
        import tempfile

        # H4/C37: the intermediate diff inputs land under the workbench tmp directory the
        # caller supplied; only a caller that supplies none falls back to the OS temp dir.
        with tempfile.TemporaryDirectory(dir=str(_TMP_DIR) if _TMP_DIR else None) as holder:
            hunks = diff_no_index(before, after, 3, Path(holder))
    for candidate in hunks:
        if candidate["new_range"] == hunk["new_range"] and candidate["old_range"] == hunk["old_range"]:
            return list(candidate.get("rows", []))
    return []


REDACTION_PREFIX = "<<redacted:sha256="


def render_line_payload(text: str, language: str) -> str:
    """Colour a code line, but never colour a redaction marker (C35)."""
    if text.startswith(REDACTION_PREFIX):
        return escape(text)
    return highlight(text, language)


def render_unit_block(
    repo: Path,
    manifest: dict[str, Any],
    entry: dict[str, Any],
    hunk: dict[str, Any],
) -> str:
    lines = unit_canonical_lines(
        unit_lines(repo, manifest["baseline"]["commit"], snapshot_dir(manifest), entry, hunk),
        hunk,
    )
    language = detect_language(entry["path"])
    if hunk["presentation"] == "diff":
        rows = render_diff_rows(repo, manifest, entry, hunk, language)
    else:
        changed = set(hunk["changed_old_lines"] if hunk["content_side"] == "old" else hunk["changed_new_lines"])
        first = int((hunk["old_range"] if hunk["content_side"] == "old" else hunk["new_range"])["start"])
        rows = [
            ("chg" if first + index in changed else "ctx", first + index, render_line_payload(line, language))
            for index, line in enumerate(lines)
        ]
    payload = render_code_rows(rows)
    if sha256_hex(normalize_code_text(payload).encode("utf-8")) != hunk["content_sha256"]:
        raise SkeletonError(
            f"unit {hunk['unit_index']} of {entry['path']}: rendered code block does not normalise "
            "back to the manifest content hash"
        )
    return f'<pre class="{CODE_BLOCK_CLASS}" data-unit="{hunk["unit_index"]}"><code>{payload}</code></pre>'


def render_diff_rows(
    repo: Path,
    manifest: dict[str, Any],
    entry: dict[str, Any],
    hunk: dict[str, Any],
    language: str,
) -> list[tuple[str, int, str]]:
    rows_in = _find_diff_hunk(repo, manifest, entry, hunk)
    if not rows_in:
        raise SkeletonError(
            f"unit {hunk['unit_index']} of {entry['path']}: unified-diff presentation requested "
            "but the hunk could not be recomputed"
        )
    header = (
        f"@@ -{int(hunk['old_range']['start'])},{int(hunk['old_range']['end']) - int(hunk['old_range']['start']) + 1}"
        f" +{int(hunk['new_range']['start'])},{int(hunk['new_range']['end']) - int(hunk['new_range']['start']) + 1} @@"
    )
    output: list[tuple[str, int, str]] = [("head", "", escape(header))]
    old_line = int(hunk["old_range"]["start"])
    new_line = int(hunk["new_range"]["start"])
    lines = unit_canonical_lines(
        unit_lines(repo, manifest["baseline"]["commit"], snapshot_dir(manifest), entry, hunk),
        hunk,
    )
    new_lines = lines if hunk["content_side"] == "new" else []
    new_cursor = 0
    for row in rows_in:
        if row == "del":
            text = redact_line(_old_line_text(repo, manifest, entry, old_line))
            output.append(("del", old_line, "-" + render_line_payload(text, language)))
            old_line += 1
        elif row == "add":
            text = new_lines[new_cursor] if new_cursor < len(new_lines) else ""
            output.append(("add", new_line, "+" + render_line_payload(text, language)))
            new_line += 1
            new_cursor += 1
        else:
            text = new_lines[new_cursor] if new_cursor < len(new_lines) else ""
            output.append(("ctx", new_line, render_line_payload(text, language)))
            new_line += 1
            new_cursor += 1
            old_line += 1
    return output


_OLD_LINE_CACHE: dict[tuple[str, str], list[str]] = {}


def _old_line_text(repo: Path, manifest: dict[str, Any], entry: dict[str, Any], line_number: int) -> str:
    key = (entry["path"], manifest["baseline"]["commit"])
    if key not in _OLD_LINE_CACHE:
        if entry.get("baseline_source") == "commit":
            payload = git_show_bytes(repo, manifest["baseline"]["commit"], entry["path"]) or b""
        else:
            payload = snapshot_bytes(snapshot_dir(manifest), entry["path"]) or b""
        _OLD_LINE_CACHE[key] = split_lines(decode_content(payload)[0])
    lines = _OLD_LINE_CACHE[key]
    index = line_number - 1
    return lines[index] if 0 <= index < len(lines) else ""



def _purpose_map(analysis: dict[str, Any]) -> dict[int, dict[str, str]]:
    """Map a unit index to its declared purpose {id, title} (A16). Optional and analysis-layer."""
    units = analysis.get("units", {}) if isinstance(analysis.get("units"), dict) else {}
    out: dict[int, dict[str, str]] = {}
    for raw_index, spec in units.items():
        if not isinstance(spec, dict):
            continue
        purpose = spec.get("purpose")
        if isinstance(purpose, dict) and str(purpose.get("id", "")).strip():
            out[int(raw_index)] = {
                "id": str(purpose["id"]).strip(),
                "title": str(purpose.get("title", purpose["id"])),
            }
    return out


def _purpose_color(purpose_id: str, purposes: list[dict[str, Any]]) -> str:
    """Map a purpose id to a --purpose-N CSS variable, cycling at PURPOSE_COLOR_CYCLE."""
    order = [str(p.get("id", "")) for p in purposes if isinstance(p, dict)]
    try:
        position = order.index(purpose_id)
    except ValueError:
        position = 0
    n = (position % PURPOSE_COLOR_CYCLE) + 1
    return f"var(--purpose-{n})"


def _purpose_list(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    purposes = analysis.get("purposes", [])
    return [p for p in purposes if isinstance(p, dict)] if isinstance(purposes, list) else []


def render_meta_badges(manifest: dict[str, Any], analysis: dict[str, Any], generated_at: str) -> str:
    badges = [
        ("strength", str(manifest["strength"]["selected"])),
        ("language", str(analysis.get("language", "en"))),
        ("generated", str(generated_at)),
        ("units", str(manifest["units_total"])),
    ]
    return "".join(
        f'<span class="report-badge"><span class="report-badge-key">{escape(key)}:</span> '
        f"{escape(value)}</span>"
        for key, value in badges
    )


def render_purposes(manifest: dict[str, Any], analysis: dict[str, Any]) -> str:
    purposes = _purpose_list(analysis)
    if not purposes:
        return '<p class="report-muted">No macro purposes are declared for this change.</p>'
    index_to_path: dict[int, str] = {}
    for entry in sorted(manifest["files"], key=lambda item: sort_key(item["path"])):
        for hunk in entry["hunks"]:
            if not hunk.get("excluded"):
                index_to_path[int(hunk["unit_index"])] = entry["path"]
    diagrams = analysis.get("diagrams", []) if isinstance(analysis.get("diagrams"), list) else []
    has_purpose_diagram = any(
        isinstance(d, dict) and d.get("id") == "diagram-purpose-map" for d in diagrams
    )
    diagram_link = (
        '<a class="report-purpose-link" href="#diagram-purpose-map">view traceability diagram &rarr;</a>'
        if has_purpose_diagram
        else ""
    )
    cards: list[str] = []
    for purpose in purposes:
        pid = str(purpose.get("id", "")).strip()
        refs = purpose.get("unit_refs", []) or []
        ref_items = "".join(
            f'<li><a href="#unit-{int(ref)}">#unit-{int(ref)} '
            f"{escape(index_to_path.get(int(ref), '?'))}</a></li>"
            for ref in refs
            if str(ref).strip().lstrip("-").isdigit()
        )
        cards.append(
            f'<article class="report-purpose-card" id="purpose-{escape(pid)}">'
            f"<h3>{escape(str(purpose.get('title', pid)))}</h3>"
            f'<div class="report-purpose-theme">{escape(str(purpose.get("theme", "")))}</div>'
            f'<p class="report-purpose-narrative">{escape(str(purpose.get("narrative", "")))}</p>'
            f"<ul>{ref_items}</ul>"
            f"{diagram_link}"
            f"</article>"
        )
    return f'<div class="report-purpose-grid">{"".join(cards)}</div>'


def render_quick_index(analysis: dict[str, Any]) -> str:
    purposes = _purpose_list(analysis)
    if not purposes:
        return '<span class="report-quick-index-label">Quick index:</span>'
    badges = "".join(
        f'<a class="report-purpose-badge" href="#purpose-{escape(str(p.get("id", "")))}">'
        f"{escape(str(p.get('title', p.get('id', ''))))}</a>"
        for p in purposes
    )
    return f'<span class="report-quick-index-label">Purposes:</span>{badges}'


def render_change_map(repo: Path, manifest: dict[str, Any], analysis: dict[str, Any]) -> str:
    pmap = _purpose_map(analysis)
    purposes = _purpose_list(analysis)
    rows: list[str] = []
    for entry in sorted(manifest["files"], key=lambda item: sort_key(item["path"])):
        for hunk in entry["hunks"]:
            if hunk["excluded"]:
                continue
            location = _code_location(hunk)
            purp = pmap.get(int(hunk["unit_index"]))
            if purp:
                color = _purpose_color(purp["id"], purposes)
                purpose_cell = (
                    f'<span class="report-purpose-tag" data-purpose="{escape(purp["id"])}" '
                    f'style="color:{color}">{escape(purp["title"])}</span>'
                )
                row_purpose = purp["id"]
            else:
                purpose_cell = '<span class="report-muted">&mdash;</span>'
                row_purpose = ""
            rows.append(
                f'<tr data-unit="{hunk["unit_index"]}" data-purpose="{escape(row_purpose)}">'
                f"<td><code>{escape(entry['path'])}</code></td>"
                f'<td><span class="report-change-kind report-change-kind-{escape(entry["change_kind"])}">'
                f"{escape(entry['change_kind'])}</span></td>"
                f"<td>{purpose_cell}</td>"
                f'<td><a href="#unit-{hunk["unit_index"]}">{hunk["unit_index"]}</a></td>'
                f"<td><code>{escape(hunk['content_sha256'][:12])}</code></td>"
                f"<td><code>{escape(location)}</code></td>"
                f'<td><a class="{ANCHOR_CLASS}" href="#unit-{hunk["unit_index"]}">analysis</a></td>'
                "</tr>"
            )
    return (
        '<table id="change-map" class="report-change-map"><thead><tr>'
        "<th>Path</th><th>Change</th><th>Purpose</th><th>Unit</th><th>Content hash</th>"
        "<th>Code location</th><th>Analysis</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def render_exclusion_table(manifest: dict[str, Any]) -> str:
    rows: list[str] = []
    excluded_files = 0
    pre_existing_regions = 0
    for entry in sorted(manifest["files"], key=lambda item: sort_key(item["path"])):
        if entry["analyzable"]:
            continue
        excluded_files += 1
    for entry in sorted(manifest["files"], key=lambda item: sort_key(item["path"])):
        if entry["analyzable"]:
            continue
        rows.append(
            '<tr data-exclude-category="{category}">'
            "<td><code>{path}</code></td><td>{category}</td><td>{reason}</td></tr>".format(
                category=escape(entry["exclude_reason"]),
                path=escape(entry["path"]),
                reason=escape(
                    f"excluded by the deterministic {entry['exclude_reason']} rule; "
                    "the path is recorded in the manifest and never counted as a unit"
                ),
            )
        )
    for entry in sorted(manifest["files"], key=lambda item: sort_key(item["path"])):
        for hunk in entry["hunks"]:
            if hunk["provenance"] != "pre_existing":
                continue
            pre_existing_regions += 1
            rows.append(
                '<tr data-exclude-category="pre_existing_change">'
                f"<td><code>{escape(entry['path'])}</code>"
                f" ({escape(hunk['old_anchor_range'])} / {escape(hunk['new_anchor_range'])})</td>"
                '<td>pre_existing_change</td>'
                "<td>the region was already modified in the worktree when the work order "
                "opened, so it is not this work order's change and is not analysed "
                f"(provenance={escape(hunk['provenance'])})</td></tr>"
            )
    return (
        '<h3 id="exclusion-heading">Excluded entries</h3>'
        f'<table id="exclusion-table"><caption>excluded files: {excluded_files}; '
        f"pre-existing regions: {pre_existing_regions}</caption><thead><tr><th>Path</th>"
        "<th>Category</th><th>Reason</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def render_toc(manifest: dict[str, Any], titles: dict[str, str], analysis: dict[str, Any]) -> str:
    pmap = _purpose_map(analysis)
    purposes = _purpose_list(analysis)
    purpose_order = [str(p.get("id", "")) for p in purposes]
    purpose_title = {
        str(p.get("id", "")): str(p.get("title", p.get("id", ""))) for p in purposes
    }
    parts: list[str] = []
    for section_id in SECTION_IDS:
        key = section_id.replace("section-", "")
        label = escape(titles.get(key, DEFAULT_SECTION_TITLES.get(key, key)))
        if key == "purposes":
            items = "".join(
                f'<li class="report-toc-unit"><a href="#purpose-{escape(pid)}">'
                f"{escape(purpose_title.get(pid, pid))}</a></li>"
                for pid in purpose_order
            )
            parts.append(
                f'<details open><summary><a href="#{section_id}">{label}</a></summary>'
                f"<ul>{items}</ul></details>"
            )
            continue
        if key == "units":
            ordered = [
                (int(hunk["unit_index"]), entry["path"])
                for entry in sorted(manifest["files"], key=lambda item: sort_key(item["path"]))
                for hunk in entry["hunks"]
                if not hunk["excluded"]
            ]
            ordered.sort(key=lambda item: item[0])
            groups: dict[str, list[tuple[int, str]]] = {pid: [] for pid in purpose_order}
            others: list[tuple[int, str]] = []
            for uid, path in ordered:
                purp = pmap.get(uid)
                if purp and purp["id"] in groups:
                    groups[purp["id"]].append((uid, path))
                else:
                    others.append((uid, path))
            items_html: list[str] = []
            for pid in purpose_order:
                items_html.append(f'<li class="report-toc-group">&#9632; {escape(purpose_title.get(pid, pid))}</li>')
                items_html.extend(
                    f'<li class="report-toc-unit"><a href="#unit-{uid}">#{uid} {escape(path)}</a></li>'
                    for uid, path in groups[pid]
                )
            if others:
                items_html.append('<li class="report-toc-group">&#9632; Other</li>')
                items_html.extend(
                    f'<li class="report-toc-unit"><a href="#unit-{uid}">#{uid} {escape(path)}</a></li>'
                    for uid, path in others
                )
            parts.append(
                f'<details open><summary><a href="#{section_id}">{label}</a></summary>'
                f"<ul>{''.join(items_html)}</ul></details>"
            )
            continue
        parts.append(f'<details open><summary><a href="#{section_id}">{label}</a></summary></details>')
    return "".join(parts)


def required_dimensions_for(change_class: str) -> tuple[str, ...]:
    """The design dimensions a change class must address (A19). Falls back to the default
    set for an unlisted or empty class; the returned keys are always in DIMENSION_LABELS."""
    return REQUIRED_DIMENSIONS.get(change_class, REQUIRED_DIMENSIONS_DEFAULT)


def render_design_lead(spec: dict[str, Any]) -> str:
    """L1 top-down lead placed before the code block (A18/A19).

    Prefers an explicit `design_lead`; otherwise composes one from the `role` and
    `motivation` dimension answers so the reader still gets the intent before the diff.
    Renders nothing when no material is available (backward compatible).
    """
    lead = str(spec.get("design_lead", "")).strip()
    if not lead:
        dims = spec.get("design_dimensions", [])
        dims = dims if isinstance(dims, list) else []
        picked: list[str] = []
        for want in ("role", "motivation"):
            for item in dims:
                if not isinstance(item, dict):
                    continue
                if str(item.get("key", "")) == want and not item.get("not_applicable"):
                    text = str(item.get("answer", "")).strip()
                    if text:
                        picked.append(text)
                    break
        lead = " ".join(picked)
    if not lead:
        return ""
    return f'<p class="report-design-lead">{escape(lead)}</p>'


def render_design_dimensions(spec: dict[str, Any]) -> str:
    """L3 per-class design dimensions (A19).

    Each declared dimension renders one `report-design-dimension` block carrying its key.
    An answered dimension shows its prose; a not-applicable dimension shows the reason marked
    as such. The builder only lays them out; V21 judges completeness against the change class.
    Renders nothing when the unit declares no dimensions (backward compatible).
    """
    dims = spec.get("design_dimensions", [])
    dims = dims if isinstance(dims, list) else []
    if not dims:
        return ""
    rows: list[str] = []
    for item in dims:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip()
        if not key:
            continue
        label = DIMENSION_LABELS.get(key, key)
        if item.get("not_applicable"):
            reason = str(item.get("reason", "")).strip()
            body = (
                '<p class="report-dimension-na">Not applicable'
                + (f": {escape(reason)}" if reason else "")
                + "</p>"
            )
        else:
            body = paragraph(str(item.get("answer", "")).strip())
        rows.append(
            f'<div class="report-design-dimension" data-dimension="{escape(key)}">'
            f"<h4>{escape(str(label))}</h4>{body}</div>"
        )
    if not rows:
        return ""
    return (
        '<div class="report-design-dimensions"><h4 class="report-dimensions-title">'
        "Design analysis</h4>" + "".join(rows) + "</div>"
    )


def _render_before_after(block: dict[str, Any], unit_index: int) -> str:
    rows_in = block.get("rows", [])
    rows_in = rows_in if isinstance(rows_in, list) else []
    body: list[str] = []
    for row in rows_in:
        if not isinstance(row, dict):
            continue
        change = str(row.get("change", "unchanged"))
        body.append(
            f'<tr data-change="{escape(change)}">'
            f'<td>{escape(str(row.get("step", "")))}</td>'
            f'<td>{escape(str(row.get("before", "")))}</td>'
            f'<td>{escape(str(row.get("after", "")))}</td>'
            f'<td>{escape(change)}</td></tr>'
        )
    title = escape(str(block.get("title", "Before vs after")))
    return (
        f'<figure class="report-depth-block" data-unit="{unit_index}" data-kind="before_after">'
        f"<figcaption>{title}</figcaption>"
        '<table class="report-depth-table"><thead><tr><th>Step</th><th>Before</th>'
        "<th>After</th><th>Change</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></figure>"
    )


def _render_lifecycle(block: dict[str, Any], unit_index: int) -> str:
    phases = block.get("phases", [])
    phases = phases if isinstance(phases, list) else []
    body: list[str] = []
    for ph in phases:
        if not isinstance(ph, dict):
            continue
        body.append(
            "<tr>"
            f'<td>{escape(str(ph.get("phase", "")))}</td>'
            f'<td><code>{escape(str(ph.get("loc", "")))}</code></td>'
            f'<td>{escape(str(ph.get("action", "")))}</td>'
            f'<td>{escape(str(ph.get("state", "")))}</td>'
            f'<td>{escape(str(ph.get("note", "")))}</td></tr>'
        )
    resource = escape(str(block.get("resource", "")))
    complete = bool(block.get("complete", False))
    flag = "complete" if complete else "incomplete"
    return (
        f'<figure class="report-depth-block" data-unit="{unit_index}" data-kind="lifecycle" '
        f'data-complete="{str(complete).lower()}">'
        f"<figcaption>Lifecycle of <code>{resource}</code> "
        f'<span class="report-lifecycle-flag">({flag})</span></figcaption>'
        '<table class="report-depth-table"><thead><tr><th>Phase</th><th>Location</th>'
        "<th>Action</th><th>State</th><th>Note</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></figure>"
    )


def _render_call_relations(block: dict[str, Any], unit_index: int) -> str:
    def side(items: Any) -> str:
        items = items if isinstance(items, list) else []
        cells = "".join(
            f'<li><span>{escape(str(it.get("label", "")))}</span> '
            f'<code>{escape(str(it.get("loc", "")))}</code></li>'
            for it in items
            if isinstance(it, dict)
        )
        return f"<ul>{cells}</ul>" if cells else '<span class="report-muted">none</span>'

    unit_label = escape(str(block.get("unit_label", "this unit")))
    return (
        f'<figure class="report-depth-block" data-unit="{unit_index}" data-kind="call_relations">'
        "<figcaption>Call relations (upstream callers &rarr; unit &rarr; downstream callees)"
        "</figcaption>"
        '<table class="report-depth-table report-callgraph"><thead><tr>'
        "<th>Callers (upstream)</th><th>Unit</th><th>Callees (downstream)</th></tr></thead>"
        f"<tbody><tr><td>{side(block.get('callers'))}</td>"
        f"<td><strong>{unit_label}</strong></td>"
        f"<td>{side(block.get('callees'))}</td></tr></tbody></table></figure>"
    )


def render_depth_blocks(spec: dict[str, Any], unit_index: int) -> str:
    """L2/L3 structured depth blocks (A20), all carried by deterministic HTML tables.

    Each block binds to its unit via data-unit and carries a data-kind from DEPTH_BLOCK_KINDS.
    The builder lays them out; V22 checks structure, the change vocabulary and the binding.
    Renders nothing when the unit declares no depth blocks (backward compatible).
    """
    blocks = spec.get("depth_blocks", [])
    blocks = blocks if isinstance(blocks, list) else []
    out: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = str(block.get("kind", ""))
        if kind == "before_after":
            out.append(_render_before_after(block, unit_index))
        elif kind == "lifecycle":
            out.append(_render_lifecycle(block, unit_index))
        elif kind == "call_relations":
            out.append(_render_call_relations(block, unit_index))
        # An unknown kind is left out here; V22 fails it from the analysis side.
    return "".join(out)

def render_units(
    repo: Path, manifest: dict[str, Any], analysis: dict[str, Any]
) -> str:
    units = analysis.get("units", {}) if isinstance(analysis.get("units"), dict) else {}
    pmap = _purpose_map(analysis)
    purposes = _purpose_list(analysis)
    purpose_units: dict[str, list[int]] = {}
    for uid, purp in pmap.items():
        purpose_units.setdefault(purp["id"], []).append(int(uid))
    for gid in purpose_units:
        purpose_units[gid].sort()
    ordered: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for entry in sorted(manifest["files"], key=lambda item: sort_key(item["path"])):
        for hunk in entry["hunks"]:
            if not hunk["excluded"]:
                ordered.append((entry, hunk))
    ordered.sort(key=lambda pair: pair[1]["unit_index"])

    parts: list[str] = []
    anchored_paths: set[str] = set()
    for position, (entry, hunk) in enumerate(ordered):
        unit_index = hunk["unit_index"]
        spec = units.get(str(unit_index), {}) if isinstance(units, dict) else {}
        if not isinstance(spec, dict):
            spec = {}
        covers = spec.get("covers") or [f"#unit-{unit_index}"]
        covers_attr = ",".join(str(item) for item in covers)
        purp = pmap.get(int(unit_index))
        data_purpose = purp["id"] if purp else ""
        parts.append(
            f'<article class="report-unit" id="unit-{unit_index}" data-unit="{unit_index}" '
            f'data-purpose="{escape(data_purpose)}" data-covers="{escape(covers_attr)}">'
        )
        if entry["path"] not in anchored_paths:
            anchored_paths.add(entry["path"])
            parts.append(
                f'<span class="report-file-anchor" id="file-{escape(file_slug(entry["path"]))}"></span>'
            )
        kind = str(entry["change_kind"])
        change_class = str(spec.get("change_class", "")).strip()
        parts.append(
            f'<header class="report-unit-head">'
            f'<h3>Unit {unit_index}: <code>{escape(entry["path"])}</code></h3>'
            f'<span class="report-change-kind report-change-kind-{escape(kind)}">{escape(kind)}</span>'
        )
        if change_class:
            parts.append(
                f'<span class="report-change-class" data-change-class="{escape(change_class)}">'
                f"{escape(change_class)}</span>"
            )
        if purp:
            color = _purpose_color(purp["id"], purposes)
            parts.append(
                f'<span class="report-purpose-tag" data-purpose="{escape(purp["id"])}" '
                f'style="color:{color}">{escape(purp["title"])}</span>'
            )
        parts.append("</header>")
        crumb_purpose = purp["title"] if purp else "Other"
        parts.append(
            f'<p class="report-breadcrumb"><a href="#section-units">Change units</a> / '
            f"{escape(crumb_purpose)} / "
            f'<a class="{ANCHOR_CLASS}" href="#unit-{unit_index}">#unit-{unit_index}</a></p>'
        )
        if purp:
            parts.append(
                f'<p><a class="report-back-to-purpose" href="#purpose-{escape(purp["id"])}">'
                f"&uarr; back to purpose: {escape(purp['title'])}</a></p>"
            )
        parts.append(
            f'<p class="report-unit-meta"><a class="{ANCHOR_CLASS}" href="#unit-{unit_index}">'
            f"#unit-{unit_index}</a> &middot; code location "
            f"<code>{escape(_code_location(hunk))}</code> &middot; content hash "
            f"<code>{escape(hunk['content_sha256'][:12])}</code></p>"
        )
        if entry.get("analyzed_as") != "work_order":
            parts.append(
                f'<p class="report-note">This file was already edited in the worktree when the '
                f"work order opened (analyzed_as={escape(entry['analyzed_as'])}); the unit above "
                "covers only the part this work order changed.</p>"
            )
        if hunk.get("overlaps_pre_existing"):
            parts.append(
                '<p class="report-note">This unit overlaps a region that was already edited '
                "before the work order opened. The overlapping region is attributed to this "
                "work order because it touched it.</p>"
            )
        if entry.get("encoding_unsupported"):
            parts.append(
                '<p class="report-note">This file is not valid UTF-8. The quoted text below was '
                "decoded with replacement characters; the original bytes are identified by the "
                "manifest source hash.</p>"
            )
        if hunk.get("redacted"):
            parts.append(
                '<p class="report-note">Secret-shaped lines in this unit were replaced by '
                "&lt;&lt;redacted:sha256=...&gt;&gt; markers. The original text is not present in "
                "this report; the marker keeps the structure recomputable.</p>"
            )
        if spec.get("note"):
            parts.append(f'<p class="report-note">{escape(str(spec["note"]))}</p>')
        # L1 design lead (A18/A19): a top-down sentence placed BEFORE the code block so the
        # reader learns the unit's role and motivation before reading the diff. It is optional
        # and drawn from `design_lead`, falling back to the role/motivation dimension answers.
        parts.append(render_design_lead(spec))
        parts.append(render_unit_block(repo, manifest, entry, hunk))
        fields = spec.get("fields", {}) if isinstance(spec.get("fields"), dict) else {}
        what_text = str(fields.get("what", "")).strip()
        if what_text:
            first_sentence = re.split(r"(?<=[.!?])\s+", what_text, maxsplit=1)[0]
            parts.append(f'<p class="report-unit-summary">{escape(first_sentence)}</p>')
        # The eight A1-A8 fields are split for readability only: the four primary fields stay
        # open, the four secondary ones fold into a native `<details>` so a long unit is not a
        # wall of text. Every field div keeps its exact `report-unit-field`/`data-field` markup
        # and stays a descendant of the unit section, so V4 still finds all eight and the A13
        # threshold is unchanged - this changes presentation, never content.
        def field_div(field: str) -> str:
            value = str(fields.get(field, "")).strip()
            return (
                f'<div class="report-unit-field" data-field="{field}">'
                f"<h4>{escape(FIELD_LABELS[field])}</h4>{paragraph(value)}</div>"
            )

        primary_open = "".join(field_div(field) for field in PRIMARY_FIELDS)
        secondary = "".join(field_div(field) for field in SECONDARY_FIELDS)
        parts.append(f'<div class="report-unit-fields">{primary_open}</div>')
        parts.append(
            '<details class="report-unit-more"><summary>More analysis '
            "(trade-offs, alternatives, business process, data and control)</summary>"
            f'<div class="report-unit-fields">{secondary}</div></details>'
        )
        # L2/L3 analysis-depth (A19/A20): the per-class design dimensions and the structured
        # depth blocks (before/after, lifecycle, call relations). Both bind to this unit and
        # neither participates in the V10 recomputation (they are context, like related code).
        parts.append(render_design_dimensions(spec))
        parts.append(render_depth_blocks(spec, unit_index))
        refs = spec.get("related_code_refs", [])
        refs = refs if isinstance(refs, list) else []
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            rpath = str(ref.get("path", ""))
            rlines = str(ref.get("lines", ""))
            rrel = str(ref.get("relation_type", ""))
            rnote = str(ref.get("note", ""))
            rcode = str(ref.get("code", ""))
            rlang = detect_language(rpath)
            parts.append(
                f'<div class="report-unit-context">'
                f"<p>{escape(rrel)}: <code>{escape(rpath)}:{escape(rlines)}</code> "
                f"{escape(rnote)} "
                f'<a class="{ANCHOR_CLASS}" href="#section-related-code">see related-code index</a></p>'
                f'<pre class="{CODE_CONTEXT_CLASS}" data-path="{escape(rpath)}" '
                f'data-lines="{escape(rlines)}" data-relation-type="{escape(rrel)}">'
                f"<code>{highlight(rcode, rlang)}</code></pre>"
                f"</div>"
            )
        previous_link = (
            f'<a href="#unit-{ordered[position - 1][1]["unit_index"]}">&larr; previous change</a>'
            if position > 0
            else "<span>previous change: none</span>"
        )
        next_link = (
            f'<a href="#unit-{ordered[position + 1][1]["unit_index"]}">next change &rarr;</a>'
            if position + 1 < len(ordered)
            else "<span>next change: none</span>"
        )
        purpose_context = ""
        if purp:
            grp = purpose_units.get(purp["id"], [])
            if int(unit_index) in grp:
                pos = grp.index(int(unit_index)) + 1
                purpose_context = (
                    f'<span class="report-purpose-context"> '
                    f"(unit {pos} of {len(grp)} in {escape(purp['title'])})</span>"
                )
        parts.append(
            f'<nav class="report-unit-nav">{previous_link}{next_link}{purpose_context}</nav>'
        )
        parts.append("</article>")
    return "".join(parts)


def render_related_code(analysis: dict[str, Any]) -> str:
    entries = analysis.get("related_code", [])
    if not isinstance(entries, list) or not entries:
        return '<p class="report-muted">No unchanged code is referenced by this report.</p>'
    parts: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        lines = str(item.get("lines", ""))
        note = str(item.get("note", ""))
        code = str(item.get("code", ""))
        language = detect_language(path)
        parts.append(
            f'<div class="report-related-code" data-path="{escape(path)}" data-lines="{escape(lines)}">'
            f"<p><code>{escape(path)}:{escape(lines)}</code> {escape(note)}</p>"
            f'<pre class="{CODE_CONTEXT_CLASS}" data-path="{escape(path)}" data-lines="{escape(lines)}">'
            f"<code>{highlight(code, language)}</code></pre></div>"
        )
    return "".join(parts)


def _derive_callgraph_spec(unit_index: int, block: dict[str, Any]) -> dict[str, Any] | None:
    """Derive a layered `flow` spec from a `call_relations` depth block (D21).

    callers (layer 0) -> the unit (layer 1) -> callees (layer 2). This is a pure function of
    the block, so the spec is deterministic; node ids are prefixed with the unit index and
    ordering is fixed. The derived diagram coexists with the table; V8 re-renders and checks it.
    """
    callers = block.get("callers") if isinstance(block.get("callers"), list) else []
    callees = block.get("callees") if isinstance(block.get("callees"), list) else []
    unit_label = str(block.get("unit_label", f"unit {unit_index}"))
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    center = f"cg{unit_index}-unit"
    for pos, item in enumerate(callers):
        if not isinstance(item, dict):
            continue
        nid = f"cg{unit_index}-caller-{pos}"
        nodes.append({"id": nid, "label": str(item.get("label", "")), "layer": 0, "kind": "theme"})
        edges.append({"from": nid, "to": center, "label": "calls"})
    nodes.append({"id": center, "label": unit_label, "layer": 1, "kind": "purpose"})
    for pos, item in enumerate(callees):
        if not isinstance(item, dict):
            continue
        nid = f"cg{unit_index}-callee-{pos}"
        nodes.append({"id": nid, "label": str(item.get("label", "")), "layer": 2, "kind": "unit"})
        edges.append({"from": center, "to": nid, "label": "calls"})
    if len(nodes) < 2:
        return None  # nothing to draw beyond the unit itself
    return {
        "id": f"diagram-callgraph-unit-{unit_index}",
        "type": "flow",
        "render_mode": "svg",
        "title": f"Call relations of {unit_label}",
        "summary": f"Upstream callers, unit {unit_index}, and downstream callees.",
        "nodes": nodes,
        "edges": edges,
    }


def _derive_before_after_specs(unit_index: int, block: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive paired before/after `flow` specs from a `before_after` depth block (D21).

    One flow chains the `before` cells, one chains the `after` cells, so the reader sees the
    old flow beside the new one. Pure and deterministic; ids prefixed by the unit index.
    """
    rows = block.get("rows") if isinstance(block.get("rows"), list) else []
    specs: list[dict[str, Any]] = []
    for side in ("before", "after"):
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, str]] = []
        prev: str | None = None
        for pos, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            text = str(row.get(side, "")).strip()
            if not text:
                continue
            nid = f"ba{unit_index}-{side}-{pos}"
            change = str(row.get("change", "unchanged"))
            kind = "purpose" if (side == "after" and change in ("added", "modified")) else "unit"
            nodes.append({"id": nid, "label": text, "layer": pos, "kind": kind})
            if prev is not None:
                edges.append({"from": prev, "to": nid, "label": ""})
            prev = nid
        if len(nodes) < 1:
            continue
        specs.append({
            "id": f"diagram-{side}-unit-{unit_index}",
            "type": "flow",
            "render_mode": "svg",
            "title": f"Unit {unit_index}: {side} flow",
            "summary": f"The {side} flow of unit {unit_index}, one step per node.",
            "nodes": nodes,
            "edges": edges,
        })
    return specs


def derive_depth_block_diagrams(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Prefer-diagrams (D21): derive flow specs from the A20 depth blocks of every unit.

    Derivation is on by default (that is the prefer-diagrams principle); a block may opt out
    with `derive_diagram: false`. The result is deterministic and ordered by unit index then by
    block position, so the diagram-spec numbering stays stable.
    """
    units = analysis.get("units", {}) if isinstance(analysis.get("units"), dict) else {}
    derived: list[dict[str, Any]] = []
    for raw_index in sorted(units, key=lambda value: int(value) if str(value).lstrip("-").isdigit() else 0):
        spec = units.get(raw_index)
        if not isinstance(spec, dict):
            continue
        try:
            unit_index = int(raw_index)
        except (TypeError, ValueError):
            continue
        blocks = spec.get("depth_blocks", [])
        blocks = blocks if isinstance(blocks, list) else []
        for block in blocks:
            if not isinstance(block, dict) or block.get("derive_diagram") is False:
                continue
            kind = str(block.get("kind", ""))
            if kind == "call_relations":
                one = _derive_callgraph_spec(unit_index, block)
                if one is not None:
                    derived.append(one)
            elif kind == "before_after":
                derived.extend(_derive_before_after_specs(unit_index, block))
    return derived


def render_diagrams(analysis: dict[str, Any]) -> str:
    specs = analysis.get("diagrams", [])
    if not isinstance(specs, list) or not specs:
        return '<p class="report-muted">No diagram is required by the change features.</p>'
    parts: list[str] = []
    for index, spec in enumerate(specs, start=1):
        if not isinstance(spec, dict):
            raise SkeletonError("diagram specs must be JSON objects")
        payload = dict(spec)
        payload.setdefault("id", f"diagram-{index}")
        rendered = render_diagram.render_diagram(payload)
        serialised = json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
        parts.append(
            f'<script type="application/json" id="diagram-spec-{index}">{serialised}</script>'
        )
        parts.append(rendered)
    return "".join(parts)


def render_verification(analysis: dict[str, Any]) -> str:
    verification = analysis.get("verification", {})
    if not isinstance(verification, dict):
        verification = {}
    commands = verification.get("commands", [])
    rows = "".join(
        f"<tr><td><code>{escape(str(item.get('command', '')))}</code></td>"
        f"<td>{escape(str(item.get('result', '')))}</td></tr>"
        for item in commands
        if isinstance(item, dict)
    )
    table = (
        "<table id=\"verification-table\"><thead><tr><th>Command</th><th>Result</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        if rows
        else '<p class="report-muted">No verification command was recorded for this work order.</p>'
    )
    return table + "<h3>Residual risk</h3>" + paragraph(str(verification.get("residual_risks", "")))


def render_glossary(analysis: dict[str, Any]) -> str:
    terms = analysis.get("glossary", [])
    if not isinstance(terms, list) or not terms:
        return '<p class="report-muted">This report defines no glossary terms.</p>'
    rows = "".join(
        f"<tr><td>{escape(str(item.get('term', '')))}</td>"
        f"<td>{escape(str(item.get('explanation', '')))}</td></tr>"
        for item in terms
        if isinstance(item, dict)
    )
    return (
        '<table id="glossary-table"><thead><tr><th>Term</th><th>Meaning in this report</th>'
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def render_report_info(manifest: dict[str, Any], analysis: dict[str, Any], generated_at: str, manifest_sha: str) -> str:
    rounds = analysis.get("rounds", [])
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('round', '')))}</td>"
        f"<td>{escape(str(item.get('refresh_reason', '')))}</td>"
        f"<td>{escape(str(item.get('scope', '')))}</td>"
        f"<td><code>{escape(str(item.get('manifest_sha256', ''))[:12])}</code></td>"
        f"<td>{escape(str(item.get('at', '')))}</td>"
        f"<td>{escape(str(item.get('sections', '')))}</td>"
        "</tr>"
        for item in rounds
        if isinstance(item, dict)
    )
    baseline = manifest["baseline"]
    strength = manifest["strength"]
    degradations = manifest.get("degradations", [])
    degradation_html = (
        "<h3>Degradations</h3><ul>"
        + "".join(f"<li><code>{escape(item)}</code></li>" for item in degradations)
        + "</ul>"
        if degradations
        else ""
    )
    notes = analysis.get("report_info", {})
    notes = notes if isinstance(notes, dict) else {}
    gate_note = str(notes.get("gate_note", "")).strip()
    skip_note = str(notes.get("skip_note", "")).strip()
    extra = ""
    if gate_note:
        extra += f'<p data-report-info="gate">{escape(gate_note)}</p>'
    if skip_note:
        extra += f'<p data-report-info="skip">{escape(skip_note)}</p>'
    return (
        '<dl class="report-info">'
        f"<dt>Generated at</dt><dd>{escape(generated_at)}</dd>"
        f"<dt>Manifest SHA-256</dt><dd><code>{escape(manifest_sha)}</code></dd>"
        f"<dt>Baseline commit</dt><dd><code>{escape(baseline['commit'])}</code></dd>"
        f"<dt>Baseline worktree digest</dt><dd><code>{escape(baseline['worktree_digest'])}</code>"
        f" ({escape(baseline['algorithm'])})</dd>"
        f"<dt>Head digest</dt><dd><code>{escape(manifest['head']['digest'])}</code> "
        f"({escape(manifest['head']['algorithm'])})</dd>"
        f"<dt>Enumeration</dt><dd><code>{escape(manifest['enumeration']['version'])}</code></dd>"
        f"<dt>Strength</dt><dd>{escape(strength['selected'])}"
        + (
            f" (upgraded from {escape(strength['requested'])}: {escape(strength['upgrade_reason'])})"
            if strength.get("upgraded")
            else ""
        )
        + "</dd>"
        f"<dt>Units</dt><dd>{manifest['units_total']}</dd>"
        f"<dt>Excluded files</dt><dd>{manifest['excluded_total']}</dd>"
        f"<dt>Pre-existing exclusions</dt><dd>{manifest['pre_existing_total']}</dd>"
        "</dl>"
        "<h3>Round records</h3>"
        '<table id="round-table"><thead><tr><th>Round</th><th>Refresh reason</th><th>Scope</th>'
        "<th>Manifest hash</th><th>At</th><th>Sections touched</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        f"{degradation_html}{extra}"
    )


def build_report(
    repo: Path,
    manifest: dict[str, Any],
    analysis: dict[str, Any],
    template_text: str,
    css_text: str,
    generated_at: str,
    manifest_bytes: bytes,
    tmp_dir: Path | None = None,
) -> str:
    # H4/C37: every intermediate file this render writes goes under the workbench tmp
    # directory the caller names; `None` is the OS temp directory fallback.
    global _TMP_DIR
    _TMP_DIR = Path(tmp_dir) if tmp_dir else None
    if int(manifest.get("schema_version", 0)) != SCHEMA_VERSION:
        raise SkeletonError("manifest schema_version does not match the supported version")
    strength = str(manifest["strength"]["selected"])
    if strength not in STRENGTHS:
        raise SkeletonError(f"unknown report strength: {strength}")
    glossary = analysis.get("glossary", [])
    if strength == "full" and (not isinstance(glossary, list) or not glossary):
        raise SkeletonError("strength 'full' requires a glossary (strength matrix)")

    # Prefer-diagrams (D21): derive flow diagram-specs from the A20 depth blocks and append them
    # to the analysis diagrams so section-diagrams renders them alongside the tables. Derivation
    # is on by default at standard/full; the minimal tier stays light and derives nothing. A
    # block opts out with `derive_diagram: false`. This is a pure, deterministic transform, so
    # the derived specs re-render byte-identically under V8.
    if strength != "minimal":
        derived = derive_depth_block_diagrams(analysis)
        if derived:
            analysis = dict(analysis)
            existing = analysis.get("diagrams", [])
            existing = list(existing) if isinstance(existing, list) else []
            analysis["diagrams"] = existing + derived

    titles = analysis.get("section_titles", {})
    titles = titles if isinstance(titles, dict) else {}
    resolved_titles: dict[str, str] = {}
    for display_index, section_id in enumerate(SECTION_IDS, start=1):
        key = section_id.replace("section-", "")
        custom = str(titles.get(key, DEFAULT_SECTION_TITLES.get(key, key)))
        resolved_titles[key] = f"{display_index}. {custom}"
    rounds = analysis.get("rounds", [])
    if not isinstance(rounds, list) or not rounds:
        rounds = [
            {
                "round": 1,
                "refresh_reason": "initial",
                "scope": "initial generation",
                "manifest_sha256": sha256_hex(manifest_bytes),
                "at": generated_at,
                "sections": "all",
            }
        ]
        analysis = dict(analysis)
        analysis["rounds"] = rounds

    replacements = {
        "DOCUMENT_LANGUAGE": escape(str(analysis.get("language", "en"))),
        "REPORT_TITLE": escape(
            str(analysis.get("title", f"Change report: {manifest['work_order_id']}"))
        ),
        "REPORT_SUBTITLE": escape(
            str(
                analysis.get(
                    "subtitle",
                    f"{manifest['units_total']} analysed change units from work order "
                    f"{manifest['work_order_id']}",
                )
            )
        ),
        "WORK_ORDER_ID": escape(manifest["work_order_id"]),
        "GENERATED_AT": escape(generated_at),
        "MANIFEST_SHA256": escape(sha256_hex(manifest_bytes)),
        "STRENGTH": escape(strength),
        "STYLE": css_text,
        "META_BADGES": render_meta_badges(manifest, analysis, generated_at),
        "TOC": render_toc(manifest, resolved_titles, analysis),
        "OVERVIEW": render_overview(manifest, analysis),
        "PURPOSES": render_purposes(manifest, analysis),
        "CHANGE_MAP": render_kind_summary(manifest) + render_change_map(repo, manifest, analysis),
        "QUICK_INDEX": render_quick_index(analysis),
        "EXCLUSION_TABLE": render_exclusion_table(manifest),
        "PROCESS_POSITION": render_process_position(analysis),
        "UNITS": render_units(repo, manifest, analysis),
        "RELATED_CODE": render_related_code(analysis),
        "DIAGRAMS": render_diagrams(analysis),
        "VERIFICATION": render_verification(analysis),
        "GLOSSARY": render_glossary(analysis),
        "REPORT_INFO": render_report_info(
            manifest, analysis, generated_at, sha256_hex(manifest_bytes)
        ),
        "FOOTER_NOTE": escape(
            str(
                analysis.get(
                    "footer_note",
                    "This report is a single self-contained file. It loads no external resource "
                    "and runs no script.",
                )
            )
        ),
    }
    for key, default in DEFAULT_SECTION_TITLES.items():
        placeholder = "SECTION_" + key.upper().replace("-", "_") + "_TITLE"
        replacements[placeholder] = escape(resolved_titles[key])

    page = template_text
    for key in PLACEHOLDERS:
        page = page.replace("{{" + key + "}}", replacements.get(key, ""))
    # G-43: the guard belongs to the template. What the replacements carried into the page is
    # content -- quoted source may legitimately contain a literal brace pair -- while a
    # placeholder-shaped token the declared set does not cover is a genuine defect.
    residue = template_residue(template_text)
    if residue:
        raise SkeletonError(
            "template placeholders remain after substitution: " + ", ".join(sorted(set(residue)))
        )
    return page


def render_overview_stats(manifest: dict[str, Any]) -> str:
    """A mechanical key-figure strip derived from the manifest (no model input).

    The values are a pure function of the coverage manifest, so the strip stays deterministic
    and adds no external resource. It gives the reader the size of the change before any prose.
    """
    stats = [
        ("Units", str(manifest["units_total"])),
        ("Excluded files", str(manifest["excluded_total"])),
        ("Pre-existing", str(manifest["pre_existing_total"])),
        ("Strength", str(manifest["strength"]["selected"])),
    ]
    cells = "".join(
        f'<div class="report-stat"><div class="report-stat-value">{escape(value)}</div>'
        f'<div class="report-stat-label">{escape(label)}</div></div>'
        for label, value in stats
    )
    return f'<div class="report-stat-grid">{cells}</div>'


def render_kind_summary(manifest: dict[str, Any]) -> str:
    """A mechanical change-kind distribution derived from the manifest (no model input).

    One analysable unit contributes to the count of its file's change kind. The proportional
    bar and the legend are pure functions of the manifest, so they stay deterministic and
    carry no external resource; the bar uses CSS variables for colour, never an image.
    """
    order = ("added", "modified", "deleted", "renamed")
    counts: dict[str, int] = {kind: 0 for kind in order}
    for entry in manifest["files"]:
        kind = str(entry.get("change_kind", ""))
        if kind not in counts:
            continue
        for hunk in entry["hunks"]:
            if not hunk.get("excluded"):
                counts[kind] += 1
    total = sum(counts.values())
    if total == 0:
        return ""
    segments = "".join(
        f'<span class="report-kind-bar-{kind}" style="width:{counts[kind] * 100 // total}%" '
        f'title="{escape(kind)}: {counts[kind]}"></span>'
        for kind in order
        if counts[kind]
    )
    legend = "".join(
        f'<span><span class="report-kind-swatch report-kind-bar-{kind}"></span>'
        f"{escape(kind)}: {counts[kind]}</span>"
        for kind in order
        if counts[kind]
    )
    return (
        '<div class="report-summary-block"><h3>Change kinds</h3>'
        f'<div class="report-kind-bar">{segments}</div>'
        f'<div class="report-kind-legend">{legend}</div></div>'
    )


def render_overview(manifest: dict[str, Any], analysis: dict[str, Any]) -> str:
    overview = analysis.get("overview", {})
    overview = overview if isinstance(overview, dict) else {}
    parts = [render_overview_stats(manifest)]
    for key, label in (
        ("what_changed", "What changed"),
        ("why", "Why it changed"),
        ("impact", "Impact"),
        ("reading_guide", "How to read this report"),
    ):
        parts.append(f"<h3>{escape(label)}</h3>{paragraph(str(overview.get(key, '')))}")
    return "".join(parts)


def render_process_position(analysis: dict[str, Any]) -> str:
    data = analysis.get("process_position", {})
    data = data if isinstance(data, dict) else {}
    parts = [paragraph(str(data.get("narrative", "")))]
    before = str(data.get("before", "")).strip()
    after = str(data.get("after", "")).strip()
    if before or after:
        parts.append(
            '<table id="process-position-table"><thead><tr><th>Before</th><th>After</th></tr>'
            f"</thead><tbody><tr><td>{escape(before)}</td><td>{escape(after)}</td></tr></tbody></table>"
        )
    return "".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the change report HTML skeleton.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--analysis", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--template", default="")
    parser.add_argument("--css", default="")
    parser.add_argument("--generated-at", default="")
    parser.add_argument(
        "--tmp-dir",
        default="",
        help=(
            "Directory for intermediate diff inputs (the workbench tmp/ directory). "
            "H4/C37 require it; when it is omitted the OS temp directory is used."
        ),
    )
    args = parser.parse_args(argv)

    skill_dir = SCRIPT_DIR.parent
    template_path = Path(args.template) if args.template else skill_dir / "assets" / "change-report-template.html"
    css_path = Path(args.css) if args.css else skill_dir / "assets" / "change-report.css"
    _OLD_LINE_CACHE.clear()

    try:
        manifest_bytes = Path(args.manifest).read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        analysis: dict[str, Any] = {}
        if args.analysis:
            analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))
            if not isinstance(analysis, dict):
                raise SkeletonError("analysis must be a JSON object")
        template_text = template_path.read_text(encoding="utf-8")
        css_text = css_path.read_text(encoding="utf-8")
        page = build_report(
            repo=Path(args.repo),
            manifest=manifest,
            analysis=analysis,
            template_text=template_text,
            css_text=css_text,
            generated_at=args.generated_at,
            manifest_bytes=manifest_bytes,
            tmp_dir=Path(args.tmp_dir) if args.tmp_dir else None,
        )
    except (SkeletonError, DiagramError, OSError, json.JSONDecodeError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # F2: a surrogate-escaped path reaches this writer intact, and an unencodable character
    # must not turn a renderable page into a crash; `page_text` renders it the way the
    # ASCII-pinned manifest spells the same bytes.
    payload = page_text(page).encode("utf-8")
    out_path.write_bytes(payload)
    print(
        json.dumps(
            {
                "ok": True,
                "report": str(out_path.resolve()),
                "bytes": len(payload),
                "units": manifest["units_total"],
                "strength": manifest["strength"]["selected"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
