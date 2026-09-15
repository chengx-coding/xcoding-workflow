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
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_manifest import (  # noqa: E402
    ANCHOR_CLASS,
    CODE_BLOCK_CLASS,
    CODE_CONTEXT_CLASS,
    FIELD_NAMES,
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
    "SECTION_CHANGE_MAP_TITLE",
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


class SkeletonError(RuntimeError):
    pass


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


def render_change_map(repo: Path, manifest: dict[str, Any]) -> str:
    rows: list[str] = []
    for entry in sorted(manifest["files"], key=lambda item: sort_key(item["path"])):
        for hunk in entry["hunks"]:
            if hunk["excluded"]:
                continue
            location = _code_location(hunk)
            rows.append(
                f'<tr data-unit="{hunk["unit_index"]}">'
                f"<td><code>{escape(entry['path'])}</code></td>"
                f"<td>{escape(entry['change_kind'])}</td>"
                f'<td><a href="#unit-{hunk["unit_index"]}">{hunk["unit_index"]}</a></td>'
                f"<td><code>{escape(hunk['content_sha256'][:12])}</code></td>"
                f"<td><code>{escape(location)}</code></td>"
                f'<td><a class="{ANCHOR_CLASS}" href="#unit-{hunk["unit_index"]}">analysis</a></td>'
                "</tr>"
            )
    return (
        '<table id="change-map" class="report-change-map"><thead><tr>'
        "<th>Path</th><th>Change</th><th>Unit</th><th>Content hash</th>"
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


def render_toc(manifest: dict[str, Any], titles: dict[str, str]) -> str:
    parts: list[str] = []
    for index, section_id in enumerate(SECTION_IDS, start=1):
        key = section_id.replace("section-", "")
        label = f"{index}. {escape(titles.get(key, DEFAULT_SECTION_TITLES.get(key, key)))}"
        if key == "units":
            items = "".join(
                f'<li><a href="#unit-{hunk["unit_index"]}">#{hunk["unit_index"]} '
                f"{escape(entry['path'])} ({escape(_code_location(hunk))})</a></li>"
                for entry in sorted(manifest["files"], key=lambda item: sort_key(item["path"]))
                for hunk in entry["hunks"]
                if not hunk["excluded"]
            )
            parts.append(
                f'<details open><summary><a href="#{section_id}">{label}</a></summary>'
                f"<ul>{items}</ul></details>"
            )
            continue
        parts.append(f'<details open><summary><a href="#{section_id}">{label}</a></summary></details>')
    return "".join(parts)


def render_units(
    repo: Path, manifest: dict[str, Any], analysis: dict[str, Any]
) -> str:
    units = analysis.get("units", {}) if isinstance(analysis.get("units"), dict) else {}
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
        covers = spec.get("covers") or [f"#unit-{unit_index}"]
        covers_attr = ",".join(str(item) for item in covers)
        parts.append(
            f'<article class="report-unit" id="unit-{unit_index}" data-unit="{unit_index}" '
            f'data-covers="{escape(covers_attr)}">'
        )
        if entry["path"] not in anchored_paths:
            anchored_paths.add(entry["path"])
            parts.append(
                f'<span class="report-file-anchor" id="file-{escape(file_slug(entry["path"]))}"></span>'
            )
        parts.append(
            f'<h3>Unit {unit_index}: <code>{escape(entry["path"])}</code> '
            f'({escape(entry["change_kind"])})</h3>'
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
        parts.append(render_unit_block(repo, manifest, entry, hunk))
        fields = spec.get("fields", {}) if isinstance(spec.get("fields"), dict) else {}
        for field in FIELD_NAMES:
            value = str(fields.get(field, "")).strip()
            parts.append(
                f'<div class="report-unit-field" data-field="{field}">'
                f"<h4>{escape(FIELD_LABELS[field])}</h4>{paragraph(value)}</div>"
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
        parts.append(f'<nav class="report-unit-nav">{previous_link}{next_link}</nav>')
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

    titles = analysis.get("section_titles", {})
    titles = titles if isinstance(titles, dict) else {}
    resolved_titles = {
        key: str(titles.get(key, DEFAULT_SECTION_TITLES[key])) for key in DEFAULT_SECTION_TITLES
    }
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
        "TOC": render_toc(manifest, resolved_titles),
        "OVERVIEW": render_overview(analysis),
        "CHANGE_MAP": render_change_map(repo, manifest),
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
    if "{{" in page or "}}" in page:
        raise SkeletonError("template placeholders remain after substitution")
    return page


def render_overview(analysis: dict[str, Any]) -> str:
    overview = analysis.get("overview", {})
    overview = overview if isinstance(overview, dict) else {}
    parts = []
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
    out_path.write_bytes(page.encode("utf-8"))
    print(
        json.dumps(
            {
                "ok": True,
                "report": str(out_path.resolve()),
                "bytes": len(page.encode("utf-8")),
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
