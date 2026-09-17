#!/usr/bin/env python3
"""Deterministic diagram rendering for `xc-change-report` (D1-D18).

Two rendering modes, decided by the diagram type:

* `flow` and `state` are drawn as inline SVG with a fixed layered geometry, integer
  coordinates, capped canvas size, capped label length and a font floor.
* `sequence`, `class` and `er` are carried by deterministic HTML tables. They are not
  drawn: the contract states plainly that these three carriers promise content
  completeness and ordering, never layout quality (D18).

The renderer never guesses. An unsupported type, a type/render-mode mismatch or a
missing node reference is an error, not a silent downgrade.

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
    DIAGRAM_TYPES,
    MAX_SVG_CANVAS_HEIGHT,
    MAX_SVG_CANVAS_WIDTH,
    MAX_TEXT_NODE_CHARS,
    SVG_FONT_SIZE,
    SVG_LAYER_GAP,
    SVG_MARGIN,
    SVG_NODE_GAP,
    SVG_NODE_HEIGHT,
    SVG_NODE_WIDTH,
    SVG_RENDER_TYPES,
    TABLE_CELL_CHARS,
)


class DiagramError(RuntimeError):
    pass


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def truncate_label(text: str) -> tuple[str, str]:
    """Return (visible, full) honouring the D14 character cap."""
    full = str(text)
    if len(full) <= MAX_TEXT_NODE_CHARS:
        return full, full
    return full[: MAX_TEXT_NODE_CHARS - 1] + "\u2026", full


def _normalise_nodes(spec: dict[str, Any]) -> list[dict[str, Any]]:
    raw = spec.get("nodes")
    if not isinstance(raw, list) or not raw:
        raise DiagramError(f"diagram {spec.get('id', '?')}: 'nodes' must be a non-empty list")
    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise DiagramError(f"diagram {spec.get('id', '?')}: node entries must be objects")
        node_id = str(item.get("id", "")).strip()
        if not node_id:
            raise DiagramError(f"diagram {spec.get('id', '?')}: node {index} has no id")
        if node_id in seen:
            raise DiagramError(f"diagram {spec.get('id', '?')}: duplicate node id {node_id}")
        seen.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "label": str(item.get("label", node_id)),
                "layer": item.get("layer"),
                "index": index,
            }
        )
    return nodes


def _normalise_edges(spec: dict[str, Any], node_ids: set[str]) -> list[dict[str, str]]:
    raw = spec.get("edges", [])
    if not isinstance(raw, list):
        raise DiagramError(f"diagram {spec.get('id', '?')}: 'edges' must be a list")
    edges: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise DiagramError(f"diagram {spec.get('id', '?')}: edge entries must be objects")
        source = str(item.get("from", "")).strip()
        target = str(item.get("to", "")).strip()
        for reference in (source, target):
            if reference not in node_ids:
                raise DiagramError(
                    f"diagram {spec.get('id', '?')}: edge references unknown node {reference!r}"
                )
        edges.append({"from": source, "to": target, "label": str(item.get("label", ""))})
    return edges


def assign_layers(nodes: list[dict[str, Any]], edges: list[dict[str, str]]) -> dict[str, int]:
    """Longest-path layering with a deterministic tie-break; explicit `layer` wins."""
    explicit = {node["id"]: node["layer"] for node in nodes if isinstance(node.get("layer"), int)}
    if len(explicit) == len(nodes):
        return {node_id: int(layer) for node_id, layer in explicit.items()}

    order = {node["id"]: node["index"] for node in nodes}
    incoming = {node["id"]: [] for node in nodes}
    for edge in edges:
        incoming[edge["to"]].append(edge["from"])

    layers: dict[str, int] = {}

    def layer_of(node_id: str, trail: frozenset[str]) -> int:
        if node_id in explicit:
            return int(explicit[node_id])
        if node_id in layers:
            return layers[node_id]
        if node_id in trail:
            return 0
        parents = incoming[node_id]
        value = 0 if not parents else max(layer_of(parent, trail | {node_id}) + 1 for parent in parents)
        layers[node_id] = value
        return value

    for node in sorted(nodes, key=lambda item: order[item["id"]]):
        layer_of(node["id"], frozenset())
    return layers


def render_svg_pages(spec: dict[str, Any]) -> list[str]:
    """Render `flow`/`state` specs into one or more inline SVG pages (D10-D17).

    Pagination is by layer groups and, when a single layer is wider than the canvas
    cap, by column windows. Nothing is scaled and nothing is dropped; edges whose two
    endpoints land on different pages are omitted from the page that misses one.
    """
    diagram_id = str(spec.get("id", "diagram"))
    nodes = _normalise_nodes(spec)
    node_ids = {node["id"] for node in nodes}
    edges = _normalise_edges(spec, node_ids)
    layers = assign_layers(nodes, edges)

    by_layer: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        by_layer.setdefault(layers[node["id"]], []).append(node)
    for layer_nodes in by_layer.values():
        layer_nodes.sort(key=lambda item: item["index"])
    ordered_layers = sorted(by_layer)

    per_page_columns = max(
        1, (MAX_SVG_CANVAS_WIDTH - 2 * SVG_MARGIN + SVG_NODE_GAP) // (SVG_NODE_WIDTH + SVG_NODE_GAP)
    )
    per_page_layers = max(
        1, (MAX_SVG_CANVAS_HEIGHT - 2 * SVG_MARGIN + SVG_LAYER_GAP) // (SVG_NODE_HEIGHT + SVG_LAYER_GAP)
    )
    widest = max(len(by_layer[layer]) for layer in ordered_layers)
    column_windows = [
        list(range(start, min(start + per_page_columns, widest)))
        for start in range(0, max(1, widest), per_page_columns)
    ]
    layer_groups = [
        ordered_layers[start : start + per_page_layers]
        for start in range(0, len(ordered_layers), per_page_layers)
    ]

    pages: list[tuple[list[tuple[int, list[dict[str, Any]]]], int]] = []
    for window in column_windows:
        window_set = set(window)
        for group in layer_groups:
            rows: list[tuple[int, list[dict[str, Any]]]] = []
            for layer in group:
                selected = [
                    node for position, node in enumerate(by_layer[layer]) if position in window_set
                ]
                if selected:
                    rows.append((layer, selected))
            if not rows:
                continue
            width = 2 * SVG_MARGIN + max(len(row) for _, row in rows) * (SVG_NODE_WIDTH + SVG_NODE_GAP) - SVG_NODE_GAP
            pages.append((rows, width))

    if len(pages) == 1:
        rows, width = pages[0]
        return [_render_svg_page(spec, diagram_id, rows, layers, edges, width)]
    return [
        _render_svg_page(spec, f"{diagram_id}-page-{number}", rows, layers, edges, width)
        for number, (rows, width) in enumerate(pages, start=1)
    ]


def _render_svg_page(
    spec: dict[str, Any],
    page_id: str,
    layer_rows: list[tuple[int, list[dict[str, Any]]]],
    layers: dict[str, int],
    edges: list[dict[str, str]],
    width: int,
) -> str:
    positions: dict[str, tuple[int, int]] = {}
    height = 2 * SVG_MARGIN + len(layer_rows) * SVG_NODE_HEIGHT + max(0, len(layer_rows) - 1) * SVG_LAYER_GAP
    for row_index, (_, row_nodes) in enumerate(layer_rows):
        y = SVG_MARGIN + row_index * (SVG_NODE_HEIGHT + SVG_LAYER_GAP)
        for column, node in enumerate(row_nodes):
            x = SVG_MARGIN + column * (SVG_NODE_WIDTH + SVG_NODE_GAP)
            positions[node["id"]] = (x, y)

    lines: list[str] = []
    visible = set(positions)
    line_records: list[str] = []
    for edge in sorted(edges, key=lambda item: (item["from"], item["to"], item["label"])):
        if edge["from"] not in visible or edge["to"] not in visible:
            continue
        source_x, source_y = positions[edge["from"]]
        target_x, target_y = positions[edge["to"]]
        start = (source_x + SVG_NODE_WIDTH // 2, source_y + SVG_NODE_HEIGHT)
        end = (target_x + SVG_NODE_WIDTH // 2, target_y)
        if end[1] > start[1]:
            path = f"M {start[0]} {start[1]} L {end[0]} {end[1]}"
        else:
            mid_y = start[1] + SVG_LAYER_GAP // 2
            path = f"M {start[0]} {start[1]} L {start[0]} {mid_y} L {end[0]} {mid_y} L {end[0]} {end[1]}"
        line_records.append(
            f'<path class="diagram-edge" d="{path}" marker-end="url(#{page_id}-arrow)" fill="none" />'
        )
        if edge["label"]:
            label, full = truncate_label(edge["label"])
            label_x = (start[0] + end[0]) // 2
            label_y = (start[1] + end[1]) // 2
            line_records.append(
                f'<text class="diagram-edge-label" x="{label_x}" y="{label_y}" '
                f'font-size="{SVG_FONT_SIZE}" text-anchor="middle">'
                f"<title>{_escape(full)}</title>{_escape(label)}</text>"
            )

    for node in sorted(positions, key=lambda item: (positions[item][1], positions[item][0])):
        x, y = positions[node]
        label = next(item["label"] for item in _normalise_nodes(spec) if item["id"] == node)
        visible_label, full_label = truncate_label(label)
        line_records.append(
            f'<rect class="diagram-node" x="{x}" y="{y}" width="{SVG_NODE_WIDTH}" '
            f'height="{SVG_NODE_HEIGHT}" rx="4" />'
        )
        line_records.append(
            f'<text class="diagram-node-label" x="{x + SVG_NODE_WIDTH // 2}" '
            f'y="{y + SVG_NODE_HEIGHT // 2 + SVG_FONT_SIZE // 2 - 1}" '
            f'font-size="{SVG_FONT_SIZE}" text-anchor="middle">'
            f"<title>{_escape(full_label)}</title>{_escape(visible_label)}</text>"
        )

    title, _ = truncate_label(str(spec.get("title", page_id)))
    summary = str(spec.get("summary", ""))
    lines.append(
        f'<svg class="report-diagram-svg" id="{_escape(page_id)}" '
        f'width="{int(width)}" height="{int(height)}" '
        f'viewBox="0 0 {int(width)} {int(height)}" role="img" '
        f'font-size="{SVG_FONT_SIZE}">'
    )
    lines.append(f"<title>{_escape(title)}</title>")
    lines.append(f"<desc>{_escape(summary)}</desc>")
    lines.append(
        f'<defs><marker id="{_escape(page_id)}-arrow" viewBox="0 0 10 10" refX="10" refY="5" '
        f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" /></marker></defs>'
    )
    lines.extend(line_records)
    lines.append("</svg>")
    return "".join(lines)


def render_table(spec: dict[str, Any], diagram_type: str) -> str:
    """Render a `sequence`/`class`/`er` spec as a deterministic HTML table plus a11y text."""
    diagram_id = str(spec.get("id", "diagram"))
    title = str(spec.get("title", diagram_id))
    summary = str(spec.get("summary", ""))
    headers, rows = _table_shape(spec, diagram_type)

    parts: list[str] = []
    parts.append(
        f'<svg class="report-diagram-a11y" width="0" height="0" role="img" '
        f'aria-hidden="true"><title>{_escape(title)}</title><desc>{_escape(summary)}</desc></svg>'
    )
    parts.append(f'<figcaption class="report-diagram-summary">{_escape(summary)}</figcaption>')
    parts.append(
        f'<table class="report-diagram-table" data-diagram-type="{_escape(diagram_type)}" '
        f'id="{_escape(diagram_id)}-table">'
    )
    parts.append("<thead><tr>" + "".join(f"<th>{_escape(item)}</th>" for item in headers) + "</tr></thead>")
    parts.append("<tbody>")
    for row in rows:
        parts.append("<tr>" + "".join(f"<td>{_escape(_clip(cell))}</td>" for cell in row) + "</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _clip(value: Any) -> str:
    text = str(value)
    if len(text) <= TABLE_CELL_CHARS:
        return text
    return text[: TABLE_CELL_CHARS - 1] + "\u2026"


def _table_shape(spec: dict[str, Any], diagram_type: str) -> tuple[list[str], list[list[str]]]:
    if diagram_type == "sequence":
        participants = spec.get("participants")
        messages = spec.get("messages")
        if not isinstance(participants, list) or not participants:
            raise DiagramError(f"diagram {spec.get('id', '?')}: 'participants' must be a non-empty list")
        if not isinstance(messages, list) or not messages:
            raise DiagramError(f"diagram {spec.get('id', '?')}: 'messages' must be a non-empty list")
        known = {str(item) for item in participants}
        rows: list[list[str]] = []
        for index, message in enumerate(messages, start=1):
            if not isinstance(message, dict):
                raise DiagramError(f"diagram {spec.get('id', '?')}: message entries must be objects")
            source = str(message.get("from", ""))
            target = str(message.get("to", ""))
            for reference in (source, target):
                if reference not in known:
                    raise DiagramError(
                        f"diagram {spec.get('id', '?')}: message references unknown participant {reference!r}"
                    )
            rows.append(
                [str(index), source, target, str(message.get("message", "")), str(message.get("note", ""))]
            )
        return ["#", "From", "To", "Message", "Note"], rows

    if diagram_type == "class":
        types = spec.get("types")
        relations = spec.get("relations", [])
        if not isinstance(types, list) or not types:
            raise DiagramError(f"diagram {spec.get('id', '?')}: 'types' must be a non-empty list")
        known = {str(item.get("name", "")) for item in types if isinstance(item, dict)}
        rows = []
        for item in types:
            if not isinstance(item, dict):
                raise DiagramError(f"diagram {spec.get('id', '?')}: type entries must be objects")
            members = item.get("members", [])
            if not isinstance(members, list):
                raise DiagramError(f"diagram {spec.get('id', '?')}: 'members' must be a list")
            rows.append(
                [
                    str(item.get("name", "")),
                    str(item.get("kind", "")),
                    "; ".join(str(member) for member in members),
                    str(item.get("note", "")),
                ]
            )
        for relation in relations if isinstance(relations, list) else []:
            if not isinstance(relation, dict):
                raise DiagramError(f"diagram {spec.get('id', '?')}: relation entries must be objects")
            source = str(relation.get("from", ""))
            target = str(relation.get("to", ""))
            for reference in (source, target):
                if reference not in known:
                    raise DiagramError(
                        f"diagram {spec.get('id', '?')}: relation references unknown type {reference!r}"
                    )
            rows.append(
                [f"{source} -> {target}", str(relation.get("kind", "")), "", str(relation.get("note", ""))]
            )
        return ["Type / relation", "Kind", "Members", "Note"], rows

    entities = spec.get("entities")
    if not isinstance(entities, list) or not entities:
        raise DiagramError(f"diagram {spec.get('id', '?')}: 'entities' must be a non-empty list")
    rows = []
    for entity in entities:
        if not isinstance(entity, dict):
            raise DiagramError(f"diagram {spec.get('id', '?')}: entity entries must be objects")
        fields = entity.get("fields", [])
        if not isinstance(fields, list):
            raise DiagramError(f"diagram {spec.get('id', '?')}: 'fields' must be a list")
        for field in fields:
            if not isinstance(field, dict):
                raise DiagramError(f"diagram {spec.get('id', '?')}: field entries must be objects")
            rows.append(
                [
                    str(entity.get("name", "")),
                    str(field.get("name", "")),
                    str(field.get("type", "")),
                    str(field.get("key", "")),
                    str(field.get("relation", "")),
                ]
            )
    if not rows:
        raise DiagramError(f"diagram {spec.get('id', '?')}: entities must declare at least one field")
    return ["Entity", "Field", "Type", "Key", "Relation"], rows


def validate_spec(spec: dict[str, Any]) -> str:
    diagram_type = str(spec.get("type", "")).strip()
    if diagram_type not in DIAGRAM_TYPES:
        raise DiagramError(
            f"diagram {spec.get('id', '?')}: unsupported diagram type {diagram_type!r} "
            f"(supported: {', '.join(DIAGRAM_TYPES)})"
        )
    render_mode = str(spec.get("render_mode", "")).strip()
    expected = "svg" if diagram_type in SVG_RENDER_TYPES else "table"
    if render_mode != expected:
        raise DiagramError(
            f"diagram {spec.get('id', '?')}: type {diagram_type!r} requires render_mode "
            f"{expected!r}, found {render_mode!r}"
        )
    return render_mode


def render_diagram(spec: dict[str, Any]) -> str:
    """Render one diagram spec into a `<figure>` fragment."""
    render_mode = validate_spec(spec)
    diagram_id = str(spec.get("id", "diagram"))
    payload = (
        "".join(render_svg_pages(spec))
        if render_mode == "svg"
        else render_table(spec, str(spec.get("type")))
    )
    return (
        f'<figure class="report-diagram" id="{_escape(diagram_id)}" '
        f'data-diagram-id="{_escape(diagram_id)}" data-diagram-type="{_escape(str(spec.get("type")))}" '
        f'data-render-mode="{_escape(render_mode)}">{payload}</figure>'
    )


def render_diagrams(specs: list[dict[str, Any]]) -> list[str]:
    return [render_diagram(spec) for spec in specs]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a change report diagram spec.")
    parser.add_argument("--spec", required=True, help="diagram spec JSON file")
    parser.add_argument("--out", default="", help="write the rendered HTML fragment here")
    args = parser.parse_args(argv)

    try:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise DiagramError("diagram spec must be a JSON object")
        payload = render_diagram(spec)
    except (DiagramError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "ok": True,
                "type": spec.get("type"),
                "render_mode": spec.get("render_mode"),
                "bytes": len(payload.encode("utf-8")),
                "html": "" if args.out else payload,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
