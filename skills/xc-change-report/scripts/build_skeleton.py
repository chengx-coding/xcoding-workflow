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
    BRIEF_PARTS,
    CHANGE_CLASSES,
    CODE_BLOCK_CLASS,
    CODE_CONTEXT_CLASS,
    DEPTH_BLOCK_KINDS,
    DEPTH_CHANGE_VOCAB,
    DIMENSION_LABELS,
    ELEMENT_BUCKETS,
    ELEMENT_KINDS,
    ELEMENT_PARTS,
    FIELD_NAMES,
    MECHANICAL_BUCKET,
    MIN_DIMENSION_CHARS,
    MIN_NA_REASON_CHARS,
    REQUIRED_DIMENSIONS,
    REQUIRED_DIMENSIONS_DEFAULT,
    RELATION_TYPES,
    SCHEMA_VERSION,
    SECTION_IDS,
    STRENGTHS,
    UNASSIGNED_BUCKET,
    diff_no_index,
    diff_tracked_path,
    decode_content,
    file_slug,
    git_show_bytes,
    normalize_code_text,
    range_is_empty,
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


class Counter:
    """A deterministic monotonic 1-based counter for page-wide diagram-spec numbering.

    One instance is shared across `render_units` (inline unit diagrams) and `render_diagrams`
    (macro diagrams) so every `diagram-spec-N` id is unique and increases in document order
    (FR-VIS-4). Determinism comes from the fixed render order, not from any global state.
    """

    def __init__(self, start: int = 1) -> None:
        self._value = start

    def next(self) -> int:
        value = self._value
        self._value += 1
        return value

# H4/C37: the workbench tmp directory the current render was asked to use. `None` means
# the caller supplied none, and only then does the process fall back to the OS temp dir.
_TMP_DIR: Path | None = None

DEFAULT_SECTION_TITLES = {
    "overview": "Overview",
    "elements": "Architectural elements",
    "change-map": "Change map",
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
    "SECTION_ELEMENTS_TITLE",
    "SECTION_CHANGE_MAP_TITLE",
    "META_BADGES",
    "ELEMENTS",
    "QUICK_INDEX",
    "SECTION_UNITS_TITLE",
    "SECTION_RELATED_CODE_TITLE",
    "SECTION_DIAGRAMS_TITLE",
    "SECTION_VERIFICATION_TITLE",
    "SECTION_GLOSSARY_TITLE",
    "SECTION_REPORT_INFO_TITLE",
    "OVERVIEW",
    "CHANGE_MAP",
    "EXCLUSION_TABLE",
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
    # An empty old range means the unit is pure insertion: there is no baseline
    # text to align a hunk against, so the unified-diff presentation is a header
    # plus one `+` row per new line. Keying this on the range rather than only on
    # `change_kind == "added"` also covers a rename whose source path is absent
    # from the baseline commit -- for example a file copied to a new path, which
    # exact-content rename pairing can classify as `renamed` while the new path
    # has no baseline blob to diff.
    if entry.get("change_kind") == "added" or range_is_empty(hunk["old_range"]):
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



# --------------------------------------------------------------------------------------
# Architectural-element layer (A22, A25-A30; H42/H49/H50)
# --------------------------------------------------------------------------------------


def _element_list(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """The declared element profiles, in declaration order (A25)."""
    elements = analysis.get("elements", [])
    return [item for item in elements if isinstance(item, dict)] if isinstance(elements, list) else []


def _element_id(element: dict[str, Any]) -> str:
    return str(element.get("id", "")).strip()


def _element_name(element: dict[str, Any]) -> str:
    identifier = _element_id(element)
    return str(element.get("name", identifier)).strip() or identifier


def _unit_element_map(analysis: dict[str, Any]) -> dict[int, str]:
    """Map a unit index to the element id (or reserved bucket) it declares (A26).

    The unit's `element_ref` is the single author binding: an element never repeats the list.
    A unit that declares nothing is absent from the map, which V34 reports as unbound.
    """
    units = analysis.get("units", {}) if isinstance(analysis.get("units"), dict) else {}
    out: dict[int, str] = {}
    for raw_index, spec in units.items():
        if not isinstance(spec, dict):
            continue
        reference = str(spec.get("element_ref", "")).strip()
        if not reference:
            continue
        try:
            out[int(raw_index)] = reference
        except (TypeError, ValueError):
            continue
    return out


def _element_color(position: int) -> str:
    """Cycle the semantic palette for an element's badge (never the only signal)."""
    return f"var(--accent-{position % 6 + 1})"


def _ordered_units(manifest: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Every analysable unit as (file entry, hunk), ordered by the global unit index."""
    ordered = [
        (entry, hunk)
        for entry in sorted(manifest["files"], key=lambda item: sort_key(item["path"]))
        for hunk in entry["hunks"]
        if not hunk["excluded"]
    ]
    ordered.sort(key=lambda pair: pair[1]["unit_index"])
    return ordered


def _unit_groups(
    manifest: dict[str, Any], analysis: dict[str, Any]
) -> list[dict[str, Any]]:
    """Group the analysable units by element (D3: elements are the spine, hunks are detail).

    Group order is the element declaration order, then the two reserved buckets, then the
    units that declare no binding at all. Inside a group the global unit order is preserved.
    """
    mapping = _unit_element_map(analysis)
    elements = _element_list(analysis)
    groups: list[dict[str, Any]] = []
    seen: set[int] = set()
    for position, element in enumerate(elements):
        identifier = _element_id(element)
        members = [
            hunk["unit_index"]
            for _, hunk in _ordered_units(manifest)
            if mapping.get(int(hunk["unit_index"])) == identifier
        ]
        seen.update(members)
        groups.append(
            {
                "key": identifier,
                "title": _element_name(element),
                "kind": str(element.get("kind", "")),
                "color": _element_color(position),
                "units": members,
                "bucket": False,
            }
        )
    for bucket in ELEMENT_BUCKETS:
        members = [
            hunk["unit_index"]
            for _, hunk in _ordered_units(manifest)
            if mapping.get(int(hunk["unit_index"])) == bucket
        ]
        seen.update(members)
        groups.append(
            {
                "key": bucket,
                "title": bucket.capitalize(),
                "kind": bucket,
                "color": "var(--text-muted)",
                "units": members,
                "bucket": True,
            }
        )
    unbound = [
        hunk["unit_index"]
        for _, hunk in _ordered_units(manifest)
        if int(hunk["unit_index"]) not in seen
    ]
    if unbound:
        groups.append(
            {
                "key": "",
                "title": "Unbound",
                "kind": "",
                "color": "var(--danger)",
                "units": unbound,
                "bucket": True,
            }
        )
    return groups


def render_meta_badges(manifest: dict[str, Any], analysis: dict[str, Any], generated_at: str) -> str:
    badges = [
        ("strength", str(manifest["strength"]["selected"])),
        ("language", str(analysis.get("language", "en"))),
        ("generated", str(generated_at)),
        ("units", str(manifest["units_total"])),
        ("elements", str(len(_element_list(analysis)))),
    ]
    return "".join(
        f'<span class="report-badge"><span class="report-badge-key">{escape(key)}:</span> '
        f"{escape(value)}</span>"
        for key, value in badges
    )


def render_brief(analysis: dict[str, Any]) -> str:
    """Render the L1 brief: three risk answers every strength must carry (A22/H50).

    All three items are always emitted, empty or not, so a missing answer is a validator
    failure (V37) instead of an invisible omission.
    """
    brief = analysis.get("brief", {})
    brief = brief if isinstance(brief, dict) else {}
    labels = {
        "worst_case": "Worst case if this ships",
        "rollback": "How to roll it back",
        "unverified": "What was not verified",
    }
    items = "".join(
        f'<div class="report-brief-item" data-brief-part="{part}">'
        f"<h3>{escape(labels[part])}</h3>"
        f"{paragraph(str(brief.get(part, '')).strip())}</div>"
        for part in BRIEF_PARTS
    )
    return f'<div class="report-brief">{items}</div>'


def _element_map_diagram(analysis: dict[str, Any]) -> dict[str, Any] | None:
    """Derive the L1 map as a `component` spec from the elements' declared relations (D27).

    A relation `{from, to, label}` means "`from` requires the interface `label` that `to`
    provides". A relation naming an undeclared element is ignored: the builder never invents
    a component, and the validator cannot see a relation that produced no node. No relation
    means no map; the element index and the profiles still carry the layer.
    """
    elements = _element_list(analysis)
    known = {_element_id(element) for element in elements}
    relations: list[dict[str, str]] = []
    for element in elements:
        declared = element.get("relations", [])
        if not isinstance(declared, list):
            continue
        for item in declared:
            if not isinstance(item, dict):
                continue
            source = str(item.get("from", "")).strip()
            target = str(item.get("to", "")).strip()
            if source not in known or target not in known or source == target:
                continue
            relations.append(
                {"from": source, "to": target, "label": str(item.get("label", "")).strip()}
            )
    if not relations:
        return None
    provides: dict[str, list[str]] = {identifier: [] for identifier in known}
    requires: dict[str, list[str]] = {identifier: [] for identifier in known}
    for relation in relations:
        label = relation["label"]
        if label and label not in requires[relation["from"]]:
            requires[relation["from"]].append(label)
        if label and label not in provides[relation["to"]]:
            provides[relation["to"]].append(label)
    components = [
        {
            "id": _element_id(element),
            "label": _element_name(element),
            "kind": str(element.get("kind", "")),
            "provides": provides[_element_id(element)],
            "requires": requires[_element_id(element)],
        }
        for element in elements
    ]
    return {
        "id": "diagram-element-map",
        "type": "component",
        "render_mode": "svg",
        "title": "Architectural element map",
        "summary": "How the changed architectural elements depend on each other and on the "
        "interfaces they provide and require.",
        "components": components,
        "connectors": relations,
    }


def render_element_index(elements: list[dict[str, Any]], groups: list[dict[str, Any]]) -> str:
    """The scannable element list that accompanies the map. One element needs no index."""
    if len(elements) <= 1:
        return ""
    counts = {group["key"]: len(group["units"]) for group in groups}
    rows = "".join(
        "<tr>"
        f'<td><a href="#element-{escape(_element_id(element))}">'
        f"{escape(_element_name(element))}</a></td>"
        f"<td>{escape(str(element.get('kind', '')))}</td>"
        f"<td>{escape(str(element.get('role', '')))}</td>"
        f"<td>{counts.get(_element_id(element), 0)}</td>"
        "</tr>"
        for element in elements
    )
    return (
        '<div class="report-table-scroll">'
        '<table id="element-index" class="report-element-index"><thead><tr>'
        "<th>Element</th><th>Kind</th><th>Role</th><th>Units</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


ELEMENT_PART_LABELS = {
    "role": "What it is",
    "before": "How it worked before",
    "after": "How it works now",
    "why": "Why it had to change",
    "contract": "Promise and boundary",
    "refs": "Where to look next",
}


def render_element_profile(
    element: dict[str, Any],
    analysis: dict[str, Any],
    index_to_path: dict[int, str],
    groups: list[dict[str, Any]],
) -> str:
    """One element profile: the six parts in the fixed H49 order, then its unit links."""
    identifier = _element_id(element)
    kind = str(element.get("kind", "")).strip()
    position = next(
        (index for index, item in enumerate(_element_list(analysis)) if _element_id(item) == identifier),
        0,
    )
    color = _element_color(position)
    parts: list[str] = [
        f'<article class="report-element" id="element-{escape(identifier)}" '
        f'data-element="{escape(identifier)}" data-element-kind="{escape(kind)}">'
        f'<header class="report-element-head">'
        f'<h3><a class="report-element-anchor" href="#element-{escape(identifier)}">'
        f"{escape(_element_name(element))}</a></h3>"
        f'<span class="report-element-kind" style="color:{color}">{escape(kind)}</span>'
        f"</header>"
    ]
    for part in ELEMENT_PARTS:
        if part == "refs":
            members = next(
                (group["units"] for group in groups if group["key"] == identifier), []
            )
            links = ", ".join(
                f'<a href="#unit-{unit}">unit {unit}'
                f" <code>{escape(index_to_path.get(unit, ''))}</code></a>"
                for unit in members
            )
            body = f"<p>{links}</p>" if links else ""
        else:
            body = paragraph(str(element.get(part, "")).strip())
        parts.append(
            f'<div class="report-element-part" data-element-part="{part}">'
            f"<h4>{escape(ELEMENT_PART_LABELS[part])}</h4>{body}</div>"
        )
    parts.append("</article>")
    return "".join(parts)


def render_elements(
    manifest: dict[str, Any], analysis: dict[str, Any], counter: "Counter | None" = None
) -> str:
    """The element section: macro lead, derived map, index, then one profile per element (H42).

    The design-topic layer renders here too, after the profiles: it is the decision record of
    this map, and its former home (the process-position section) no longer exists.
    """
    counter = counter if counter is not None else Counter()
    elements = _element_list(analysis)
    groups = _unit_groups(manifest, analysis)
    index_to_path = {
        int(hunk["unit_index"]): entry["path"] for entry, hunk in _ordered_units(manifest)
    }
    parts: list[str] = []
    process_position = analysis.get("process_position", {})
    if isinstance(process_position, dict):
        narrative = str(process_position.get("narrative", "")).strip()
        if narrative:
            parts.append(f'<p class="report-elements-lead">{escape(narrative)}</p>')
    diagram = _element_map_diagram(analysis)
    if diagram is not None:
        parts.append(
            '<div class="report-element-map">'
            + _render_diagram_block(diagram, counter, "diagram-element-map")
            + "</div>"
        )
    if not elements:
        parts.append(
            '<p class="report-muted">No architectural elements are declared for this change; '
            "the change map and the unit sections carry the analysis.</p>"
        )
        parts.append(_render_design_topics(analysis, counter))
        return "".join(parts)
    parts.append(render_element_index(elements, groups))
    for element in elements:
        parts.append(render_element_profile(element, analysis, index_to_path, groups))
    parts.append(_render_design_topics(analysis, counter))
    return "".join(parts)


def render_quick_index(analysis: dict[str, Any]) -> str:
    elements = _element_list(analysis)
    if not elements:
        return '<span class="report-quick-index-label">Quick index:</span>'
    badges = "".join(
        f'<a class="report-element-badge" href="#element-{escape(_element_id(item))}">'
        f"{escape(_element_name(item))}</a>"
        for item in elements
    )
    return f'<span class="report-quick-index-label">Elements:</span>{badges}'


def render_change_map(repo: Path, manifest: dict[str, Any], analysis: dict[str, Any]) -> str:
    mapping = _unit_element_map(analysis)
    elements = {_element_id(item): item for item in _element_list(analysis)}
    rows: list[str] = []
    for entry in sorted(manifest["files"], key=lambda item: sort_key(item["path"])):
        for hunk in entry["hunks"]:
            if hunk["excluded"]:
                continue
            location = _code_location(hunk)
            reference = mapping.get(int(hunk["unit_index"]), "")
            element = elements.get(reference)
            if element is not None:
                position = next(
                    (
                        index
                        for index, item in enumerate(_element_list(analysis))
                        if _element_id(item) == reference
                    ),
                    0,
                )
                element_cell = (
                    f'<span class="report-element-tag" data-element="{escape(reference)}" '
                    f'style="color:{_element_color(position)}">'
                    f"{escape(_element_name(element))}</span>"
                )
            elif reference:
                element_cell = (
                    f'<span class="report-element-tag report-element-bucket" '
                    f'data-element="{escape(reference)}">{escape(reference)}</span>'
                )
            else:
                element_cell = '<span class="report-muted">&mdash;</span>'
            rows.append(
                f'<tr data-unit="{hunk["unit_index"]}" data-element="{escape(reference)}">'
                f"<td><code>{escape(entry['path'])}</code></td>"
                f'<td><span class="report-change-kind report-change-kind-{escape(entry["change_kind"])}">'
                f"{escape(entry['change_kind'])}</span></td>"
                f"<td>{element_cell}</td>"
                f'<td><a href="#unit-{hunk["unit_index"]}">{hunk["unit_index"]}</a></td>'
                f"<td><code>{escape(hunk['content_sha256'][:12])}</code></td>"
                f"<td><code>{escape(location)}</code></td>"
                f'<td><a class="{ANCHOR_CLASS}" href="#unit-{hunk["unit_index"]}">analysis</a></td>'
                "</tr>"
            )
    return (
        '<div class="report-table-scroll">'
        '<table id="change-map" class="report-change-map"><thead><tr>'
        "<th>Path</th><th>Change</th><th>Element</th><th>Unit</th><th>Content hash</th>"
        "<th>Code location</th><th>Analysis</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
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
        '<div class="report-table-scroll">'
        f'<table id="exclusion-table"><caption>excluded files: {excluded_files}; '
        f"pre-existing regions: {pre_existing_regions}</caption><thead><tr><th>Path</th>"
        "<th>Category</th><th>Reason</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
    )


def render_toc(manifest: dict[str, Any], titles: dict[str, str], analysis: dict[str, Any]) -> str:
    elements = _element_list(analysis)
    groups = _unit_groups(manifest, analysis)
    index_to_path = {
        int(hunk["unit_index"]): entry["path"] for entry, hunk in _ordered_units(manifest)
    }
    parts: list[str] = []
    for section_id in SECTION_IDS:
        key = section_id.replace("section-", "")
        label = escape(titles.get(key, DEFAULT_SECTION_TITLES.get(key, key)))
        if key == "elements":
            items = "".join(
                f'<li class="report-toc-unit"><a href="#element-{escape(_element_id(item))}">'
                f"{escape(_element_name(item))}</a></li>"
                for item in elements
            )
            topics = (
                analysis.get("design", {}).get("topics", [])
                if isinstance(analysis.get("design"), dict)
                else []
            )
            topics = topics if isinstance(topics, list) else []
            items += "".join(
                f'<li class="report-toc-topic"><a href="#design-topic-{escape(str(topic.get("id", "")))}">'
                f'{escape(str(topic.get("title", topic.get("id", ""))))}</a></li>'
                for topic in topics
                if isinstance(topic, dict) and str(topic.get("id", "")).strip()
            )
            parts.append(
                f'<details open><summary><a href="#{section_id}">{label}</a></summary>'
                f"<ul>{items}</ul></details>"
            )
            continue
        if key == "units":
            items_html: list[str] = []
            for group in groups:
                if not group["units"]:
                    continue
                heading = (
                    f'<a href="#element-{escape(group["key"])}">{escape(group["title"])}</a>'
                    if not group["bucket"]
                    else escape(group["title"])
                )
                items_html.append(f'<li class="report-toc-group">&#9632; {heading}</li>')
                items_html.extend(
                    f'<li class="report-toc-unit"><a href="#unit-{unit}">#{unit} '
                    f"{escape(index_to_path.get(unit, ''))}</a></li>"
                    for unit in group["units"]
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
    """A20 before/after block as a full-width stacked comparison (not a narrow table).

    Each step is one `report-ba-step` card carrying `data-change`; inside it a before panel and
    an after panel sit side by side on a wide viewport and stack on a narrow one. Long prose
    therefore gets the full content width instead of being crushed into a table cell (the P2
    overflow root cause). The block still carries `data-kind="before_after"` and `data-unit`, and
    each step still carries `data-change` from DEPTH_CHANGE_VOCAB, so V22 binds unchanged.
    """
    rows_in = block.get("rows", [])
    rows_in = rows_in if isinstance(rows_in, list) else []
    dash = '<p class="report-muted">&mdash;</p>'
    steps: list[str] = []
    for row in rows_in:
        if not isinstance(row, dict):
            continue
        change = str(row.get("change", "unchanged"))
        step = str(row.get("step", "")).strip()
        before = str(row.get("before", "")).strip()
        after = str(row.get("after", "")).strip()
        head = (
            '<div class="report-ba-step-head">'
            f'<span class="report-ba-step-name">{escape(step) or "&middot;"}</span>'
            f'<span class="report-ba-change report-ba-change-{escape(change)}">{escape(change)}</span>'
            "</div>"
        )
        panels = (
            '<div class="report-ba-panels">'
            '<div class="report-ba-panel report-ba-before">'
            '<span class="report-ba-label">Before</span>'
            f'{paragraph(before) if before else dash}</div>'
            '<div class="report-ba-panel report-ba-after">'
            '<span class="report-ba-label">After</span>'
            f'{paragraph(after) if after else dash}</div>'
            "</div>"
        )
        steps.append(
            f'<div class="report-ba-step" data-change="{escape(change)}">{head}{panels}</div>'
        )
    title = escape(str(block.get("title", "Before vs after")))
    return (
        f'<figure class="report-depth-block" data-unit="{unit_index}" data-kind="before_after">'
        f"<figcaption>{title}</figcaption>"
        f'<div class="report-ba-steps">{"".join(steps)}</div>'
        "</figure>"
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
        '<div class="report-table-scroll">'
        '<table class="report-depth-table"><thead><tr><th>Phase</th><th>Location</th>'
        "<th>Action</th><th>State</th><th>Note</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div></figure>"
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
        '<div class="report-table-scroll">'
        '<table class="report-depth-table report-callgraph"><thead><tr>'
        "<th>Callers (upstream)</th><th>Unit</th><th>Callees (downstream)</th></tr></thead>"
        f"<tbody><tr><td>{side(block.get('callers'))}</td>"
        f"<td><strong>{unit_label}</strong></td>"
        f"<td>{side(block.get('callees'))}</td></tr></tbody></table></div></figure>"
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

def _design_topics(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    if "design" not in analysis:
        return []
    design = analysis.get("design")
    if not isinstance(design, dict):
        raise SkeletonError("analysis.design must be an object when supplied")
    if "topics" not in design or not isinstance(design.get("topics"), list) or not design["topics"]:
        raise SkeletonError("analysis.design.topics must be a non-empty list when design is supplied")
    topics = design.get("topics", [])
    if any(not isinstance(topic, dict) for topic in topics):
        raise SkeletonError("analysis.design.topics entries must be objects")
    return topics


def _topic_refs_by_unit(analysis: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    for topic in _design_topics(analysis):
        topic_id = str(topic.get("id", "")).strip()
        if not topic_id:
            continue
        refs = topic.get("unit_refs", [])
        if not isinstance(refs, list):
            continue
        for ref in refs:
            try:
                out.setdefault(int(ref), []).append(topic)
            except (TypeError, ValueError):
                continue
    return out


def render_units(
    repo: Path, manifest: dict[str, Any], analysis: dict[str, Any],
    counter: "Counter | None" = None, derive_diagrams: bool = True,
) -> str:
    """Render the unit sections grouped by architectural element (D3/H9).

    The element is the grouping level and the hunk stays the analysis unit: the coverage proof
    is defined over units, so folding them is a presentation change only. Every unit keeps its
    own `#unit-N` anchor and its eight fields as descendants of the unit section, so V2/V3/V4/V10
    still find exactly what they found before.
    """
    counter = counter if counter is not None else Counter()
    units = analysis.get("units", {}) if isinstance(analysis.get("units"), dict) else {}
    topic_map = _topic_refs_by_unit(analysis)
    groups = _unit_groups(manifest, analysis)
    ordered = _ordered_units(manifest)
    by_index = {hunk["unit_index"]: (entry, hunk) for entry, hunk in ordered}
    # H23: prev/next follows the rendered (element-grouped) order, not the numeric unit order.
    render_order = [unit for group in groups for unit in group["units"]]
    positions = {unit: index for index, unit in enumerate(render_order)}

    parts: list[str] = []
    anchored_paths: set[str] = set()
    for group_index, group in enumerate(groups):
        if not group["units"]:
            continue
        heading_name = (
            escape(group["title"])
            if group["bucket"]
            else f'<a href="#element-{escape(group["key"])}">{escape(group["title"])}</a>'
        )
        heading_kind = (
            ""
            if group["bucket"]
            else f' <span class="report-element-kind" style="color:{group["color"]}">'
            f'{escape(group["kind"])}</span>'
        )
        parts.append(
            f'<h3 class="report-unit-group" id="unit-group-{group_index}" '
            f'data-unit-group="{escape(group["key"])}">{heading_name}{heading_kind}'
            f'<span class="report-unit-group-count"> {len(group["units"])} unit(s)</span></h3>'
        )
        for unit_index in group["units"]:
            entry, hunk = by_index[unit_index]
            spec = units.get(str(unit_index), {}) if isinstance(units, dict) else {}
            if not isinstance(spec, dict):
                spec = {}
            covers = spec.get("covers") or [f"#unit-{unit_index}"]
            covers_attr = ",".join(str(item) for item in covers)
            reference = str(group["key"])
            parts.append(
                f'<article class="report-unit" id="unit-{unit_index}" data-unit="{unit_index}" '
                f'data-element="{escape(reference)}" data-covers="{escape(covers_attr)}">'
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
            if not group["bucket"]:
                parts.append(
                    f'<span class="report-element-tag" data-element="{escape(reference)}" '
                    f'style="color:{group["color"]}">{escape(group["title"])}</span>'
                )
            parts.append("</header>")
            fields = spec.get("fields", {}) if isinstance(spec.get("fields"), dict) else {}
            what_text = str(fields.get("what", "")).strip()
            if what_text:
                first_sentence = re.split(r"(?<=[.!?])\s+", what_text, maxsplit=1)[0]
                parts.append(f'<p class="report-unit-summary">{escape(first_sentence)}</p>')
            parts.append('<details class="report-unit-detail">')
            parts.append(f"<summary>Unit {unit_index} detail: code, analysis and diagrams</summary>")
            parts.append(
                f'<p class="report-breadcrumb"><a href="#section-units">Change units</a> / '
                f'{escape(group["title"])} / '
                f'<a class="{ANCHOR_CLASS}" href="#unit-{unit_index}">#unit-{unit_index}</a></p>'
            )
            if not group["bucket"]:
                parts.append(
                    f'<p><a class="report-back-to-element" href="#element-{escape(reference)}">'
                    f"&uarr; back to element: {escape(group['title'])}</a></p>"
                )
            topic_links = topic_map.get(int(unit_index), [])
            if topic_links:
                links = ", ".join(
                    f'<a class="report-back-to-topic" href="#design-topic-{escape(str(topic.get("id", "")))}">'
                    f'{escape(str(topic.get("title", topic.get("id", ""))))}</a>'
                    for topic in topic_links
                )
                parts.append(f'<p class="report-topic-context">Design topics: {links}</p>')
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
            parts.append(render_design_lead(spec))
            parts.append(render_unit_block(repo, manifest, entry, hunk))

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
            parts.append(render_design_dimensions(spec))
            parts.append(render_depth_blocks(spec, unit_index))
            if derive_diagrams:
                for diagram_spec in unit_diagram_specs(spec, unit_index):
                    parts.append(
                        '<div class="report-unit-diagram">'
                        + _render_diagram_block(diagram_spec, counter, f"diagram-unit-{unit_index}")
                        + "</div>"
                    )
            author_unit_diagrams = [
                diagram
                for diagram in (
                    analysis.get("diagrams", [])
                    if isinstance(analysis.get("diagrams"), list)
                    else []
                )
                if isinstance(diagram, dict)
                and str(diagram.get("unit", "")) == str(unit_index)
                and not diagram.get("topic")
            ]
            for diagram_spec in author_unit_diagrams:
                parts.append(
                    '<div class="report-unit-diagram report-author-unit-diagram">'
                    + _render_diagram_block(diagram_spec, counter, f"diagram-unit-{unit_index}-author")
                    + "</div>"
                )
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
            position = positions[int(unit_index)]
            previous_link = (
                f'<a href="#unit-{render_order[position - 1]}">&larr; previous change</a>'
                if position > 0
                else "<span>previous change: none</span>"
            )
            next_link = (
                f'<a href="#unit-{render_order[position + 1]}">next change &rarr;</a>'
                if position + 1 < len(render_order)
                else "<span>next change: none</span>"
            )
            group_context = ""
            if not group["bucket"] and int(unit_index) in group["units"]:
                group_position = group["units"].index(int(unit_index)) + 1
                group_context = (
                    f'<span class="report-element-context"> '
                    f"(unit {group_position} of {len(group['units'])} in {escape(group['title'])})</span>"
                )
            parts.append(
                f'<nav class="report-unit-nav">{previous_link}{next_link}{group_context}</nav>'
            )
            parts.append("</details>")
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
        "unit": unit_index,
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
            "unit": unit_index,
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


def _diagram_registry(analysis: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Materialize author and derived specs so topic refs resolve before unit rendering."""
    specs = analysis.get("diagrams", [])
    specs = specs if isinstance(specs, list) else []
    registry: dict[str, dict[str, Any]] = {}
    for spec in [item for item in specs if isinstance(item, dict)] + derive_depth_block_diagrams(analysis):
        diagram_id = str(spec.get("id", "")).strip()
        if not diagram_id:
            continue
        if diagram_id in registry and registry[diagram_id] != spec:
            raise SkeletonError(f"duplicate diagram id with conflicting specs: {diagram_id}")
        registry[diagram_id] = spec
    return registry


def _render_diagram_block(spec: dict[str, Any], counter: "Counter", fallback_id: str) -> str:
    """Render one diagram spec into its `diagram-spec-N` script block plus its `<figure>`.

    `counter` assigns the page-wide sequential N so that diagrams inlined into unit blocks and
    diagrams left in the macro section share one monotonic numbering in document order (D21/
    FR-VIS-4). The figure id comes from the spec's own `id` (a derived unit diagram carries a
    `*-unit-N` id), never from N, so V8 keeps matching spec to figure by id regardless of where
    the figure sits on the page.
    """
    if not isinstance(spec, dict):
        raise SkeletonError("diagram specs must be JSON objects")
    payload = dict(spec)
    payload.setdefault("id", fallback_id)
    number = counter.next()
    rendered = render_diagram.render_diagram(payload)
    serialised = json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    return (
        f'<script type="application/json" id="diagram-spec-{number}">{serialised}</script>'
        + rendered
    )


def unit_diagram_specs(spec: dict[str, Any], unit_index: int) -> list[dict[str, Any]]:
    """Derive the unit-level diagram specs for one unit's A20 depth blocks (D21).

    These are the diagrams that must render inline inside `#unit-<unit_index>` (FR-VIS-4). A block
    opts out with `derive_diagram: false`. Pure and deterministic; the ids carry `-unit-N` so the
    near-content validator can bind each figure to its unit.
    """
    blocks = spec.get("depth_blocks", [])
    blocks = blocks if isinstance(blocks, list) else []
    derived: list[dict[str, Any]] = []
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


def render_diagrams(analysis: dict[str, Any], counter: "Counter | None" = None) -> str:
    """Render the macro / cross-unit diagrams that belong in `section-diagrams` (H11).

    Only author-provided diagrams that are NOT bound to a single unit are rendered here; the
    unit-level derived diagrams are inlined into their unit blocks by `render_units` (FR-VIS-4).
    An author diagram may still be routed to a unit by carrying a `"unit"` field, in which case it
    is skipped here. `counter` provides the shared page-wide diagram-spec numbering.
    """
    counter = counter if counter is not None else Counter()
    specs = analysis.get("diagrams", [])
    specs = specs if isinstance(specs, list) else []
    topic_ids = {
        str(ref)
        for topic in _design_topics(analysis)
        for ref in (topic.get("diagram_refs", []) if isinstance(topic.get("diagram_refs", []), list) else [])
    }
    # H48: one canonical render owner per figure. The element map is derived and rendered inside
    # section-elements, so an author diagram carrying the same id must not render a second time.
    mapped_ids = {"diagram-element-map"}
    macro = [
        s for s in specs
        if isinstance(s, dict)
        and s.get("unit") is None
        and str(s.get("id", "")) not in topic_ids
        and str(s.get("id", "")) not in mapped_ids
    ]
    if not macro:
        return '<p class="report-muted">No macro or cross-unit diagram is required by the change features.</p>'
    parts: list[str] = []
    for index, spec in enumerate(macro, start=1):
        parts.append(_render_diagram_block(spec, counter, f"diagram-{index}"))
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
    snapshot = baseline.get("worktree_snapshot", {})
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    # H14: the capture scope is a reader-visible fact, not a manifest-only one. It is what lets
    # a reader tell a proportional snapshot (the commit already held every clean byte) from a
    # broken one, so the scope the manifest published is rendered here and V5 asserts it.
    scope = str(snapshot.get("scope", "") or "")
    captured = snapshot.get("captured_paths")
    # The scope carries the id V5 reads, so the check asserts the value the manifest published
    # rather than a word that the strength row could satisfy by coincidence.
    scope_html = (
        f'<dt>Baseline capture scope</dt><dd id="baseline-capture-scope">{escape(scope)}'
        + (f" ({escape(str(captured))} captured path(s))" if captured is not None else "")
        + "</dd>"
        if scope
        else ""
    )
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
    mapping = _unit_element_map(analysis)
    mechanical_units = sum(1 for value in mapping.values() if value == MECHANICAL_BUCKET)
    unassigned_units = sum(1 for value in mapping.values() if value == UNASSIGNED_BUCKET)
    element_count = len(_element_list(analysis))
    # H14/A22 honesty: the report states whether a human confirmed it. "none" is the default
    # because the human gate is closed by default; a report must never imply review it did not get.
    confirmation = str(notes.get("human_confirmation", "none")).strip() or "none"
    if confirmation == "none":
        confirmation_text = (
            "This report has not been confirmed by a human reviewer; the accuracy review worker "
            "and the mechanical checks are the evidence it carries."
        )
    else:
        confirmation_text = f"Human confirmation: {confirmation}."
    extra = (
        f'<p data-report-info="human-confirmation" data-human-confirmation="{escape(confirmation)}">'
        f"{escape(confirmation_text)}</p>"
    )
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
        + scope_html
        + f"<dt>Head digest</dt><dd><code>{escape(manifest['head']['digest'])}</code> "
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
        f'<dt>Architectural elements</dt><dd><span data-report-count="elements">'
        f"{element_count}</span></dd>"
        f'<dt>Mechanical units</dt><dd><span data-report-count="mechanical">'
        f"{mechanical_units}</span></dd>"
        f'<dt>Unassigned units</dt><dd><span data-report-count="unassigned">'
        f"{unassigned_units}</span></dd>"
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

    # Prefer-diagrams (D21) + inline placement (FR-VIS-4): the diagrams derived from a unit's A20
    # depth blocks are rendered inline inside that unit by render_units (see unit_diagram_specs),
    # not appended to analysis["diagrams"]; section-diagrams keeps only the macro / cross-unit
    # author diagrams. The minimal tier derives nothing. One page-wide counter numbers every
    # diagram-spec-N in document order across the inline unit diagrams and the macro section.
    diagram_counter = Counter()
    derive_unit_diagrams = strength != "minimal"

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
        "ELEMENTS": render_elements(manifest, analysis, diagram_counter),
        "CHANGE_MAP": render_kind_summary(manifest) + render_change_map(repo, manifest, analysis),
        "QUICK_INDEX": render_quick_index(analysis),
        "EXCLUSION_TABLE": render_exclusion_table(manifest),
        "UNITS": render_units(
            repo, manifest, analysis, diagram_counter, derive_unit_diagrams
        ),
        "RELATED_CODE": render_related_code(analysis),
        "DIAGRAMS": render_diagrams(analysis, diagram_counter),
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


def render_overview_stats(manifest: dict[str, Any], analysis: dict[str, Any]) -> str:
    """A mechanical key-figure strip derived from the manifest and the element count.

    The values are a pure function of the manifest and the declared elements, so the strip stays
    deterministic and adds no external resource. It gives the reader the size of the change and
    the number of architectural elements before any prose.
    """
    stats = [
        ("Units", str(manifest["units_total"])),
        ("Elements", str(len(_element_list(analysis)))),
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
    parts = [render_overview_stats(manifest, analysis), render_brief(analysis)]
    for key, label in (
        ("what_changed", "What changed"),
        ("why", "Why it changed"),
        ("impact", "Impact"),
        ("reading_guide", "How to read this report"),
    ):
        parts.append(f"<h3>{escape(label)}</h3>{paragraph(str(overview.get(key, '')))}")
    return "".join(parts)


def _render_design_topics(
    analysis: dict[str, Any], counter: "Counter | None" = None
) -> str:
    topics = _design_topics(analysis)
    if not topics:
        return ""
    counter = counter if counter is not None else Counter()
    by_id = _diagram_registry(analysis)
    rendered: set[str] = set()
    parts = ['<nav class="report-design-index" aria-label="Design topics"><strong>Design topics</strong><ul>']
    parts.extend(
        f'<li><a href="#design-topic-{escape(str(topic.get("id", "")))}">'
        f'{escape(str(topic.get("title", topic.get("id", ""))))}</a></li>'
        for topic in topics
        if str(topic.get("id", "")).strip()
    )
    parts.append("</ul></nav>")
    for topic in topics:
        topic_id = str(topic.get("id", "")).strip()
        if not topic_id:
            continue
        title = str(topic.get("title", topic_id)).strip()
        kind = str(topic.get("kind", "")).strip()
        parts.append(
            f'<article class="report-design-topic" id="design-topic-{escape(topic_id)}" '
            f'data-topic-kind="{escape(kind)}"><h3>{escape(title)}</h3>'
        )
        summary = str(topic.get("summary", "")).strip()
        if summary:
            parts.append(f'<p class="report-design-topic-summary">{escape(summary)}</p>')
        for key, label in (("current", "Current"), ("target", "Target"), ("decision", "Decision")):
            value = str(topic.get(key, "")).strip()
            if value:
                parts.append(f'<h4>{escape(label)}</h4>{paragraph(value)}')
        boundaries = topic.get("boundaries", [])
        if isinstance(boundaries, list) and boundaries:
            items = "".join(f"<li>{escape(str(item))}</li>" for item in boundaries if str(item).strip())
            if items:
                parts.append(f'<details class="report-design-details"><summary>Boundaries</summary><ul>{items}</ul></details>')
        refs = topic.get("unit_refs", [])
        if isinstance(refs, list) and refs:
            links = ", ".join(f'<a href="#unit-{escape(str(ref))}">unit-{escape(str(ref))}</a>' for ref in refs)
            parts.append(f'<p class="report-topic-units">Implementation units: {links}</p>')
        element_refs = topic.get("element_refs", [])
        if isinstance(element_refs, list) and element_refs:
            links = ", ".join(
                f'<a href="#element-{escape(str(ref))}">element-{escape(str(ref))}</a>'
                for ref in element_refs
            )
            parts.append(f'<p class="report-topic-elements">Elements: {links}</p>')
        evidence = topic.get("evidence", [])
        if isinstance(evidence, list) and evidence:
            rows = []
            for item in evidence:
                if not isinstance(item, dict):
                    continue
                ref = str(item.get("ref", "")).strip()
                ref_html = f'<a href="{escape(ref)}">{escape(ref)}</a>' if ref.startswith("#") else f"<code>{escape(ref)}</code>"
                reason = str(item.get("reason", "")).strip()
                rows.append(
                    f'<li><strong>{escape(str(item.get("kind", "")))}</strong> '
                    f'<span class="report-evidence-status">{escape(str(item.get("status", "")))}</span> '
                    f"{ref_html}{(' &mdash; ' + escape(reason)) if reason else ''}</li>"
                )
            if rows:
                parts.append('<details class="report-design-details"><summary>Evidence</summary><ul class="report-design-evidence">' + "".join(rows) + "</ul></details>")
        diagram_refs = topic.get("diagram_refs", [])
        if isinstance(diagram_refs, list):
            for diagram_id in diagram_refs:
                diagram_id = str(diagram_id).strip()
                spec = by_id.get(diagram_id)
                if spec is None:
                    parts.append(f'<p class="report-note">Diagram reference unavailable: <code>{escape(diagram_id)}</code></p>')
                    continue
                if spec.get("unit") is not None:
                    parts.append(f'<p class="report-topic-diagram-link">Diagram: <a href="#{escape(diagram_id)}"><code>{escape(diagram_id)}</code></a> (rendered in its unit)</p>')
                    continue
                if diagram_id in rendered:
                    parts.append(f'<p class="report-topic-diagram-link">Shared diagram: <a href="#{escape(diagram_id)}"><code>{escape(diagram_id)}</code></a></p>')
                    continue
                spec = dict(spec)
                spec.setdefault("topic", topic_id)
                parts.append('<div class="report-design-diagram">' + _render_diagram_block(spec, counter, diagram_id) + '</div>')
                rendered.add(diagram_id)
        parts.append("</article>")
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
