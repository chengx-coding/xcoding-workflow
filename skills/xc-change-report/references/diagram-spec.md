# Diagram Specification

Grammar and rendering contract for the report's diagrams. Specifications are embedded in the
report; no diagram source file (`.mmd`, `.puml`, `.svg`) is ever written next to it.

## Two carriers, five types

The renderer is deliberately tiered rather than uniformly capable. A fixed-geometry layered
layout is enough for a flow or a state machine; sequence, class and ER diagrams need label
placement and edge routing that this Skill does not implement and will not pretend to
implement.

| Type | Carrier | Layout guarantee | Mechanically checked |
|---|---|---|---|
| `flow` | inline SVG (layered) | yes, D14-D17 | type, node references, render success, geometry, golden fixture |
| `state` | inline SVG (layered) | yes, D14-D17 | the same |
| `sequence` | deterministic HTML table (participants x ordered messages) | none; the table promises message order and correct participants only | structured carrier exists, participants and messages resolve, cell length cap, non-empty content |
| `class` | deterministic HTML table (types x members x relations) | none; the table does not promise an inheritance layout | the same |
| `er` | deterministic HTML table (entities x fields x keys x relations) | none | the same |

`render_mode` is `svg` for `flow` and `state`, `table` for `sequence`, `class` and `er`. A
mismatch is a validation failure, not a silent downgrade.

## Trigger conditions

Triggers are change features, not task size.

- **D1** Multi-step business processes or cross-module calls: a flow diagram is required.
- **D2** Timed interaction between two or more participants or systems: a sequence diagram is
  required.
- **D3** New or changed types, interfaces, inheritance or composition: a class diagram is
  required.
- **D4** Persistence structures, table structures or entity relations: an ER diagram is
  required.
- **D5** An explicit state machine or state field: a state diagram is required.
- **D6** None of the above (a constant or wording change, for example): nothing is required.

Whether a diagram *should* exist for a given change is a substantive judgement about the
change, and therefore a human review item. The mechanical part is that a diagram which is
present is well-formed and truthful about its carrier.

## Specification format

- **D7** The model never writes SVG or table HTML by hand. It writes a structured specification
  and the script renders it deterministically.
- **D8** The specification lives inside the report as
  `<script type="application/json" id="diagram-spec-N">…</script>`. This is the only `<script>`
  exception, and its predicate is mechanical (H36): any script whose `type` is not
  `application/json` fails, and an allowed JSON block must have an id of the form
  `diagram-spec-N` and no attribute other than `type` and `id`.
- **D9** Exactly five types are supported: `flow`, `sequence`, `class`, `er`, `state`. A sixth
  type is an error: no guessing, no degradation. "Supported" means "has a defined carrier", not
  "drawn as SVG": `svg` mode accepts only `flow` and `state`.
- **D10** The SVG renderer uses a layered layout and emits pure SVG (`<rect>`, `<path>`,
  `<text>`, `<line>`). All coordinates sit on the integer grid, and the same specification
  always renders to the same bytes. Text escaping uses the standard library's HTML escaping.
  Inline SVG carries no `xmlns` attribute: it is unnecessary inside an HTML document and would
  itself be a URL text hit under H33.
- **D11** Every diagram (SVG or table) carries `<title>`, `<desc>` and a visible text summary,
  so it stays readable in a text-only or assistive context.
- **D12** Both the specification and the rendering are validated: the type is supported, the
  referenced nodes exist, the render mode matches the type, rendering does not raise, and an
  SVG diagram satisfies D14-D17.
- **D13** The specification is archived inside the report and nowhere else. There is no
  source file to fall out of sync with the report: to change a diagram, change the
  specification block in the report and re-render. An intermediate rendering that must be
  written to disk goes under `<workbench>/tmp/` and is never declared as an artefact.
- **D14** Text cap: a single text node holds at most `MAX_TEXT_NODE_CHARS = 40` characters.
  Longer text is truncated with an ellipsis and the full text goes into that node's `<title>`.
  Unbounded text and overflow out of a fixed-width box are both forbidden.
- **D15** Canvas cap: an SVG is at most `MAX_SVG_CANVAS_WIDTH = 1400` user units wide and
  `MAX_SVG_CANVAS_HEIGHT = 1400` tall. Beyond that the script paginates, one SVG per page, with
  ids of the form `diagram-N-page-M`. Fonts are never scaled down and nothing overflows
  horizontally. Pagination splits by layer group first and by column window second; an edge
  whose endpoints land on different pages is omitted from the page that is missing one, which
  is the documented cost of staying inside the cap.
- **D16** Font floor: font size is a constant and is never below `MIN_SVG_FONT_SIZE = 11` user
  units (`SVG_FONT_SIZE = 12` is the rendered size). Row spacing, column spacing and the
  minimum gap between adjacent nodes in a layer are constants too, so nodes never overlap.
- **D17** Golden artefacts: `flow` and `state` each have a golden SVG fixture under
  `tests/fixtures/change_report/diagrams/`. Rendering the same specification twice must be
  byte-identical, and it must equal the golden file. Changing the renderer deliberately means
  regenerating the fixture in the same change.
- **D18** What is not promised is written into the contract instead of being left for the
  reader to discover: the `sequence`, `class` and `er` table carriers promise no layout
  quality. The script can only decide that a structured carrier exists, that the referenced
  participants or types exist, that text stays inside the cap and that content is not empty.
  Whether a table really expresses timing semantics or an inheritance relation is a human
  review item. The renderer draws no geometry for these three types and never accepts "degrade
  to a bad SVG" as an outcome.
- **D19** A purpose-traceability diagram reuses the `flow` carrier and its layered SVG
  geometry (no new diagram type; D9 stays at exactly five types). Its nodes carry an
  optional `kind` of `purpose`, `theme` or `unit`, placed on explicit `layer` values
  `0`/`1`/`2`. The renderer colours each node purely by `kind`: `purpose` uses the accent
  primary, `theme` the accent secondary, and `unit` a neutral surface. Edges may run
  purpose-to-theme, theme-to-unit, or purpose-to-unit directly (the existing skip-layer
  orthogonal routing). The geometry constants D14-D17 are reused unchanged; a node without
  `kind` renders byte-identically to an ordinary flow node.

## Geometry constants

All constants live in `scripts/build_manifest.py` and are imported by `render_diagram.py`.

| Constant | Value | Purpose |
|---|---|---|
| `MAX_TEXT_NODE_CHARS` | 40 | per-text-node character cap (D14) |
| `MAX_SVG_CANVAS_WIDTH` | 1400 | canvas width cap (D15) |
| `MAX_SVG_CANVAS_HEIGHT` | 1400 | canvas height cap (D15) |
| `MIN_SVG_FONT_SIZE` | 11 | font floor (D16) |
| `SVG_FONT_SIZE` | 12 | rendered font size |
| `SVG_NODE_WIDTH` / `SVG_NODE_HEIGHT` | 220 / 46 | node box size |
| `SVG_NODE_GAP` | 40 | minimum gap between nodes in a layer (D16) |
| `SVG_LAYER_GAP` | 90 | vertical gap between layers (D16) |
| `SVG_MARGIN` | 24 | canvas margin |
| `SVG_CHAR_WIDTH` | 7 | label width estimate used for layout only |
| `TABLE_CELL_CHARS` | 120 | per-cell cap for table carriers |

## Layout rules

- Layers come from an explicit integer `layer` on each node when every node has one;
  otherwise they are computed by longest-path layering over the edges, with a deterministic
  tie-break by the node's position in the specification. Cycles terminate at layer 0.
- Nodes inside a layer keep their specification order. Edges are sorted by
  `(from, to, label)` before rendering.
- Coordinates are `margin + index * (size + gap)` and are therefore always integers.
- An edge between adjacent layers is a straight line from the source's bottom centre to the
  target's top centre. An edge that skips or reverses a layer is routed with an orthogonal
  path through a mid-layer row.
- Rendering is a pure function of the specification: no clock, no randomness, no host
  dependency. This is what makes the golden fixtures meaningful.

## Table carriers

Each of the three table types renders a `<figure>` containing an accessibility `<svg>` with
`<title>` and `<desc>`, a visible summary (`report-diagram-summary`) and a
`<table class="report-diagram-table">` with a fixed header row:

- `sequence`: `#`, `From`, `To`, `Message`, `Note`. Participants must be declared and every
  message endpoint must name one.
- `class`: `Type / relation`, `Kind`, `Members`, `Note`. Relations are appended as rows and
  both endpoints must name a declared type.
- `er`: `Entity`, `Field`, `Type`, `Key`, `Relation`. Every entity must declare at least one
  field.

An empty or unresolvable structure is an error. The renderer sorts nothing inside these
carriers: their order is the specification's order, so the rendered table is reproducible.
