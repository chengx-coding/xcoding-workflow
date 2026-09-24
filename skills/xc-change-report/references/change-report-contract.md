# Change Report Structure and Analysis Contract

Normative contract for the single-file report. Identifiers are addresses: the H, A, V, C and
D numbers below are cited by the scripts, the validator's failure messages and the tests.
Implementation constants named here live in `scripts/build_manifest.py`.

## Position and naming

- **H1** The deliverable path is `<workbench>/artifacts/<report-node-id>/change-report.html`.
  Both placeholders come from engine return values; never join them by hand.
- **H2** The coverage manifest is `change-report-manifest.json` in the same directory.
- **H2a** The accuracy verdicts are `change-report-verdicts.json` in the same directory. The
  three files always share one directory.
- **H3** `change-report.html` is a single file: double-click opens it; no server, no network,
  no adjacent file, no `assets/` directory.
- **H4** The report is never written into the project repository. Intermediate files live
  under `<workbench>/tmp/` and are never declared as artefacts.
- **H5** The node declares these paths as `--artifact` in its runtime terminal state and
  declares `metadata.artifact.audience=user` with
  `metadata.artifact.content_language=work_order.document_language`.

## Page structure (fixed order, no additions, no reordering)

Sections carry these exact ids; the validator reads the order from the document. H42 is
inserted after H6 and before H7; H6-H14 are not renumbered (their addresses are stable).

| H | Section id | Content |
|---|---|---|
| H6 | `section-overview` | executive summary: top what/why/impact, metadata badges, reading guide |
| **H42** | `section-purposes` | the macro purposes the change serves: one concept card per purpose (title, theme, narrative, unit anchors), linking to the purpose-map diagram |
| H7 | `section-change-map` | the change map and the exclusion table |
| H8 | `section-process-position` | where the change sits in the wider flow, before/after |
| H9 | `section-units` | one section per analysable change unit |
| H10 | `section-related-code` | unchanged code quoted to explain context |
| H11 | `section-diagrams` | diagrams required by the change features |
| H12 | `section-verification` | referenced verification commands, results, residual risk |
| H13 | `section-glossary` | every proper noun used in the body, explained once |
| H14 | `section-report-info` | generation time, manifest hash, baseline, rounds, skips, degradations |

H6-H12 and H14 are judged mechanically (V5). The completeness of H13 and the writing quality
of H6-H12 are human review items; no script decides whether a term was really explained.

## Change map

- **H15** One row per analysable change unit.
- **H16** Seven columns, in this order: repository-relative path, change kind, purpose tag,
  unit number, first 12 hex characters of the manifest content hash, code location, link to
  the unit's analysis section. The purpose tag (A16) is the unit's purpose id; a unit with no
  purpose renders an empty tag cell. The code location is `<path>:<start>-<end>` taken from
  `new_range`, or from `old_range` for a unit whose content side is the old side (a pure
  deletion). V5 asserts both the row count and that the code-location column is non-empty;
  V18 asserts the purpose tag matches the unit's declared purpose.
- **H17** The change-map row count equals the manifest's `units_total`. Excluded files are
  not counted here and do not appear; the equation performs no subtraction.
- **H18** Excluded entries have their own table with path, category and reason per row, plus
  the totals. Its row count equals `excluded_total + pre_existing_total`. Exclusions are
  never hidden in the manifest only.

## Table of contents and anchors

- **H19** The left sidebar is a fixed three-level table of contents: section, then purpose
  group, then change unit, collapsible. Section level is always visible; purpose groups group
  units by purpose without reordering the globally monotonic unit anchors. V20 asserts every
  section, purpose group and unit target exists with no dangling or extra unit.
- **H20** Collapsing uses native HTML (`<details>`/`<summary>`) and CSS only. No JavaScript.
- **H21** Every analysable unit has the stable anchor `#unit-<unit_index>`, where
  `<unit_index>` is the manifest's globally monotonic unit number, not a per-file restart and
  not a git hunk number. File-level anchors are `#file-<file-slug>`.
- **H22** `<file-slug>` is built by the script: take the repository-relative path, lowercase
  it, replace `/`, `\`, `.` and every non-alphanumeric character with `-`, then collapse runs
  of `-`. The model never writes an anchor by hand.
- **H23** Cross-references inside the page use in-page anchors. Every unit section carries a
  previous/next change navigation, a breadcrumb and a "back to purpose" link to its H42
  purpose card (`#purpose-<purpose_id>`). prev/next still follow the global unit order across
  purpose groups, never truncating at a group boundary. V18 asserts the bidirectional
  purpose-to-unit and unit-to-purpose links are not dangling.
- **H24** Table-of-contents entries and anchors are validated: every table-of-contents target
  exists, every manifest anchor exists in the page, and no unit section exists outside the
  manifest.
- **H24a** The anchor-to-unit correspondence is surjective: each analysable unit has exactly
  one `#unit-<unit_index>` section. H24 rules out extras; V2 rules out omissions.

## Per-unit analysis content (all eight fields are required)

- **A1** `what` - what the code does, in words a human reads without the diff.
- **A2** `why` - the problem it solves; what would happen without it.
- **A3** `design` - the approach or pattern, and how it cooperates with existing code.
- **A4** `tradeoffs` - what was given up; what it costs.
- **A5** `flow-position` - which stage, module or layer of the wider flow it belongs to.
- **A6** `alternatives` - what else was considered and why it was not chosen.
- **A7** `business-process` - the business or domain process it takes part in.
- **A8** `data-and-control` - how it is called, its inputs and outputs, error and boundary
  handling.
- **A9** Granularity is the change unit: one unit, one analysis covering that unit's whole
  diff. Never one blob per file, never one paragraph per diff line.
- **A10** Joint analysis is allowed: several units may share one analysis, but the section
  must list every covered anchor in its `data-covers` attribute. The check runs on anchor
  sets (V2, V3), not on paragraph counts.
- **A11** Unchanged code may be quoted for context with `report-code-context`, which must
  carry the file path and a line range in `data-path` and `data-lines` and is visually
  distinct from changed code. It never participates in hash recomputation.
- **A12** A pure addition only has to explain why it is needed; a pure deletion only has to
  explain why it can go and what replaces it. A1-A8 still apply otherwise.
- **A13** The minimum information threshold is enforced by the validator from one built-in
  constant table:
  - `MIN_FIELD_CHARS = 40` characters after whitespace removal, per field;
  - `PLACEHOLDER_TOKENS` = `todo`, `tbd`, `fixme`, `n/a`, `xxx`, `placeholder`,
    `lorem ipsum`, `待补充`, `待定` - a field whose text is, or contains, one of these as a
    standalone token fails;
  - a field made only of symbols or with no word content fails.
- **A14** Analysis must be bound to the code it cites, by two mechanical rules:
  - V10 recomputes the unit's content hash from its code block and compares it with the
    manifest;
  - V11 requires at least one code token of the unit's diff to appear in the analysis prose.
  The length threshold (A13) only prevents blanks; A14 prevents filler.
- **A15** Binding failure and content error are different things. A14 can decide "this text
  has nothing to do with this code"; it cannot decide "this text explains the code wrongly".
  That is the accuracy review worker's judgement, with the human gate as an extra layer when
  it is open. V14 recomputes the verdict file at the final stage: it checks that every
  analysable unit is covered, that the verdict vocabulary is respected and that the
  thresholds hold. It cannot check whether a verdict is right, and the three statements are
  never merged.
- **A16** `purpose` ties a unit to the macro purpose it serves: `{"id": "p1",
  "title": "…"}`, linking to the H42 card `#purpose-<id>`. The title narrative is at least
  `MIN_PURPOSE_CHARS = 20` non-whitespace characters. `purpose` is optional (analysis JSON
  written before this layer exists still loads); it does **not** participate in the V11 token
  intersection. V17 enforces purpose integrity and V18 enforces the purpose tag in the
  change map.
- **A17** `related_code_refs` lists unchanged code quoted inside the unit as one or more
  `report-code-context` blocks: `{"path", "lines", "note", "relation_type", "code"}`.
  `relation_type` is a closed enumeration `caller | callee | data-structure | contract`.
  These blocks never participate in V10; V20 enforces their `data-path`/`data-lines` and
  relation type.

## Analysis-depth layer (A18-A20)

The analysis-depth layer makes a unit explain a change **top-down, design to implementation**.
The full change taxonomy, the per-class design questions and their sources are enumerated in
`references/analysis-depth.md`; the items below are the contract increment the scripts enforce.
All three fields are optional, so analysis written before this layer still loads and V21/V22 stay
vacuous for a unit that declares no change class.

- **A18** `change_class` is the unit's change-taxonomy label, a member of the closed set
  `CHANGE_CLASSES` in `scripts/build_manifest.py` (`member-var`, `constant-config`, `data-schema`,
  `global-state`, `function`, `signature`, `control-flow`, `call-dependency`, `type-contract`,
  `api-contract`, `concurrency`, `error-handling`, `di-lifecycle`, `performance`, `refactor`,
  `test-config`, `other`). It renders a `report-change-class` badge in the unit head carrying
  `data-change-class`. V21 rejects a declared class outside the set.
- **A19** `design_dimensions` is a list of the design questions the unit's class must address.
  Each item is `{"key", "answer"}` or `{"key", "not_applicable": true, "reason"}`; `key` is one of
  `DIMENSION_LABELS` and the dimensions a class must address are `REQUIRED_DIMENSIONS[class]`
  (falling back to `REQUIRED_DIMENSIONS_DEFAULT`). A required dimension is satisfied in exactly one
  of three states: **answered** (text >= `MIN_DIMENSION_CHARS` = 40 non-whitespace characters),
  **not applicable** (`not_applicable=true` with a reason >= `MIN_NA_REASON_CHARS` = 12
  characters), or it is **missing** and V21 fails. A dimension renders one
  `report-design-dimension` block carrying `data-dimension`; the six-layer skeleton's `role`/
  `motivation` also feed the L1 `report-design-lead` rendered before the code block.
  `design_dimensions` do not participate in V10 or V11. V21 enforces this three-state discipline;
  it never judges whether an answer is correct.
- **A20** `depth_blocks` is a list of structured, deterministic **HTML-table** blocks, each a
  member of `DEPTH_BLOCK_KINDS` (`before_after`, `lifecycle`, `call_relations`). A `before_after`
  block is a step table whose `change` column is drawn from `DEPTH_CHANGE_VOCAB`
  (`added|removed|modified|unchanged`); a `lifecycle` block is a phase table with a `complete`
  flag; a `call_relations` block is a `callers | unit | callees` table. Every block renders a
  `report-depth-block` figure carrying `data-unit` and `data-kind`. Depth blocks are context: they
  never participate in V10, add no SVG geometry and no golden fixture, and load no external
  resource. V22 enforces their kind, unit binding and change vocabulary.
- **A21** Prefer-diagrams authoring/review default: when the information content is comparable, a
  diagram is more readable than prose, so the report author and reviewer prefer a diagram wherever
  one is a good fit (a multi-step or cross-module flow, a call topology, a state machine, a schema,
  a type relationship). This is a default with a judgement, not a mandate: a light change (a
  constant, a piece of copy, D6) may carry no diagram, and whether a diagram should exist for a
  given change is a human review item. The mechanical support is deliberately non-blocking: the
  A20 depth blocks derive `flow` diagrams automatically (D21), `sequence` offers an optional real
  SVG carrier (D22), and a unit of a diagram-preferred change class that provides no diagram and
  does not waive the diagram-relevant dimensions earns a non-blocking advisory (D20) - never a
  failure. "No diagram" is never a hard error; the per-change-class suitability map lives in
  `references/analysis-depth.md` and the diagram mechanisms in `references/diagram-spec.md`.
## Code references, diffs and highlighting

- **H25** Every analysable unit has at least one code block showing its diff, and exactly one
  block per unit is the recomputation object: `class="report-code"` with
  `data-unit="<unit_index>"`.
- **H26** Code is quoted verbatim from the repository: no rewriting, reordering or completion.
  The complete after-state snippet appears in `<pre><code>` with real line numbers. There are
  exactly two exceptions, and both must be visibly marked:
  - (a) content matching the C34 sensitive rules is replaced by redaction markers; the original
    bytes survive only as hashes and lengths;
  - (b) content that is not valid UTF-8 is decoded with replacement characters and the unit is
    annotated.
- **H26a** The recomputation normalisation is fixed:
  1. take the inner HTML of the unit's `<pre class="report-code"><code>` element;
  2. drop the line-number column, which the script emits as
     `<span class="report-lineno">N</span>` followed by one literal tab;
  3. drop rows marked `report-diff-head`;
  4. drop rows marked `report-diff-del`;
  5. strip one leading `+` from rows marked `report-diff-add`;
  6. unwrap `report-code-changed` markers, keeping their text;
  7. remove all remaining markup, decode entities, keep every other space and newline;
  8. encode as UTF-8 and take the SHA-256.
  Steps 3-5 exist so that the snippet presentation and the unified-diff presentation reduce
  to the same text (H27). `scripts/build_manifest.py` owns this implementation;
  `scripts/build_skeleton.py` and `scripts/validate_report.py` import it, so the forward and
  reverse directions cannot drift.
- **H27** The default presentation is the complete after-state snippet with the changed lines
  marked. When the snippet is longer than `MAX_UNIT_LINES_SNIPPET = 60`, or when the changed
  lines are not contiguous inside the unit's range, the unified-diff presentation is used
  instead: a `@@ -old,+new @@` header plus `+`/`-` rows. Both presentations must normalise to
  the same text, otherwise V10 fails. Units whose content side is the old side (pure
  deletions) always use the snippet presentation, because dropping their rows would normalise
  to nothing.
- **H28** The class names are contract: `report-code`, `report-code-changed`,
  `report-code-context`, `report-diff-add`, `report-diff-del`, `report-anchor`. The purpose
  layer adds `report-meta-badges`, `report-purpose-card`, `report-purpose-tag`,
  `report-purpose-badge`, `report-quick-index`, `report-unit-head`, `report-unit-summary`,
  `report-unit-context`, `report-breadcrumb`, `report-back-to-purpose`. The presentation
  rebuild adds, for readability only, `report-stat-grid`/`report-stat` (the mechanical
  overview key-figure strip), `report-summary-block`/`report-kind-bar`/`report-kind-legend`
  (the mechanical change-kind distribution derived from the manifest), `report-unit-fields`
  (the per-unit field wrapper) and `report-unit-more` (the native `<details>` that folds the
  four secondary A1-A8 fields). The analysis-depth layer (A18-A20) adds `report-change-class`
  (the A18 badge carrying `data-change-class`), `report-design-lead` (the L1 lead rendered
  before the code block), `report-design-dimensions`/`report-design-dimension`/
  `report-dimension-na` (the A19 dimensions, carrying `data-dimension`), and
  `report-depth-block`/`report-depth-table`/`report-callgraph`/`report-lifecycle-flag` (the A20
  structured tables, carrying `data-unit` and `data-kind`). The depth classes carry no
  `report-code` and never enter the V10 recomputation. These carry no analysis content of their
  own and gate no
  mechanical check; every A1-A8 field div keeps its exact `report-unit-field`/`data-field`
  markup and stays a descendant of its unit section, so V4 still finds all eight fields and
  the A13 threshold is unchanged. The inlined stylesheet provides the styling and the
  validator checks that the contract classes are used. `report-code-context` is A11/A17
  context and never participates in V10.
- **H29** Highlighting is a lightweight lexical colourer inside the script: comments,
  strings, numbers and a generic keyword set, emitted as `<span class="tok-*">`. Colours come
  from the inlined stylesheet.
- **H30** No Pygments, highlight.js, Prism, Shiki or any other external highlighter, and no
  network lookup of language definitions.
- **H31** The language is chosen by file extension. An unknown extension or an unsupported
  language degrades to escaped monospace text: no error, no interruption.
- **H32** Colouring is a pure function: the same text and language label always produce
  byte-identical output. The colourer never changes the code text, only wraps it in spans, so
  code quoting stays verbatim even when the colouring is imperfect. **"Coloured" is not
  "syntactically correct":** the keyword set is generic, not a grammar per language, and this
  is an accepted, documented cost.

## Offline self-containment

- **H33** No external resource and no fetch capability may be *constructed*. Any hit in this
  enumeration fails:
  - URL text: `http://`, `https://`, and protocol-relative addresses starting with `//`;
  - external subresources: any `<link>`, `<script src=...>`, `<img src=...>`,
    `<img srcset=...>`, `<source src=...>`, `<video>`, `<audio>`, `<track>`,
    `<input type="image">`;
  - embedding and fetching: `<iframe>` (with or without `src`), `<object data=...>`,
    `<embed src=...>`, `<meta http-equiv="refresh">`, `<base href=...>`, `<form action=...>`,
    and any element carrying `action` or `formaction`;
  - CSS: `url(...)` and `@import` (including `@import url(...)`, `@import "..."`, and
    `@font-face` sources) in the inlined `<style>` and in any `style` attribute;
  - SVG: `<image href=...>`, `<image xlink:href=...>`, `<use href=...>`,
    `<use xlink:href=...>`, `<feImage>` - except same-document references whose value starts
    with `#`.
  Inline SVG therefore carries no `xmlns` attribute: it is not needed inside an HTML document
  and it would itself be a URL text hit. CSS comments are stripped before the `url(...)` and
  `@import` scan, because a comment cannot fetch anything.
- **H33a** Nothing on the page needs the network to display and nothing can start a fetch.
  H33 is the checkable decomposition of this sentence; the two are not redundant.
- **H34** Styles are inlined in `<style>`. No web font; system font stacks only.
- **H35** Diagrams are carried as described in `diagram-spec.md`: `flow` and `state` as inline
  SVG, `sequence`, `class` and `er` as deterministic HTML tables. Neither carrier needs a
  script runtime or an external resource.
- **H36** The `<script>` predicate is mechanical: **every `<script>` whose `type` is not
  `application/json` fails.** A JSON script block that is allowed must also have an id of the
  form `diagram-spec-N`, no `src`, and no attribute other than `type` and `id`.
- **H37** The validator enforces H33-H36 textually and structurally; the result enters the
  node completion check.
- **H37a** Code-block exclusion zone: text inside `report-code`, `report-code-changed`,
  `report-code-context`, `report-diff-add` and `report-diff-del` does not participate in the
  H33 URL-text scan. The rule is an element-interval exclusion, not a regex exemption: the
  validator computes the character interval of every excluded element in document order and
  discards matches that start inside one. **The interval is the element's own parsed subtree,
  never a blanket remainder**: an element the author never closed is bounded by the first
  structural boundary it owns, so an unclosed code block cannot exempt the rest of the page.
  Two reasons: H26 requires verbatim quoting, so a URL
  in a quoted constant, comment or docstring is data; and a `src`/`data`/`href` value can only
  appear on a real tag's attribute, never inside quoted code text. The reverse also holds: a
  bare URL outside a code block still fails.
- **H37b** The validator distinguishes elements from text with a structured parser
  (`html.parser` tag and data callbacks). It never guesses tag boundaries with one large
  regex. Regular expressions are used only for CSS declarations, and only on the text of
  `<style>` elements and `style` attributes.

## Language and audience

- **H38** The body language is `work_order.document_language`. Code, paths, identifiers,
  commands and machine output stay verbatim and are not translated.
- **H39** The single source of truth for writing rules is the public `xc-document`
  "Default Human-Readable Authoring" contract, including the four ISO 24495-1 principles:
  relevant, findable, understandable, usable. This Skill does not restate them; it cites them,
  so the two cannot drift apart.
- **H40** This Skill declares only its increment over that contract:
  - HTML presentation: section order (H6-H14), class names (H28), anchor rules (H21, H22),
    native-only collapsing (H20);
  - glossary correspondence: the glossary entry set and the in-place first-use explanations in
    the body must correspond one to one (H13);
  - diagram summaries: every diagram carries `<title>`, `<desc>` and a visible text summary
    (D11);
  - navigation: every unit section carries previous/next change links (H23).
- **H41** The audience is `user` (the human work order owner), so the report is not an internal
  English artefact and must follow the work order's document language. This Skill's `SKILL.md`
  carries the public phrase `public \`xc-document\` human-readable authoring default` so the
  repository's authoring-contract assertion covers it.

## Purpose-layer and analysis-depth validation

- **V17** Purpose integrity: when a unit carries an A16 purpose, H42 must render a purpose
  card for every referenced purpose, every purpose card references at least one real unit,
  and every unit purpose resolves to an existing card. When no unit has a purpose the check
  is vacuous (backward compatible).
- **V18** Cross-reference closure: the change-map purpose tag for each unit equals that
  unit's declared purpose id; the purpose-card-to-unit, unit-to-purpose and related-code
  links are not dangling.
- **V19** Three-level TOC completeness: every section, purpose group and unit target in the
  TOC exists, and no unit is listed twice or omitted.
- **V20** Context block validity: every `report-code-context` block carries non-empty
  `data-path` and `data-lines`, its `relation_type` is in the closed enumeration, and the
  blocks are excluded from the V10 recomputation selection.
- **V21** Design-dimension completeness (A18/A19): when a unit declares a `change_class`, the
  class must be in `CHANGE_CLASSES`, and every dimension in `REQUIRED_DIMENSIONS[class]` renders a
  `report-design-dimension` inside that unit in one of two accepted states -- answered (text
  >= `MIN_DIMENSION_CHARS`) or not-applicable with a reason (>= `MIN_NA_REASON_CHARS`). A missing
  required dimension fails. A unit with no `change_class` is vacuous (backward compatible). V21
  proves the dimension was addressed, never that the answer is correct.
- **V22** Depth-block validity (A20): every `report-depth-block` carries a `data-kind` in
  `DEPTH_BLOCK_KINDS` and a `data-unit` naming an analysable unit; a `before_after` row's
  `data-change` is in `DEPTH_CHANGE_VOCAB`; depth blocks are excluded from the V10 recomputation
  selection. Renders-nothing units stay vacuous.

## Strength matrix

The level is fixed by confirmed facts, never by task length or wording, and is written to
`report.strength` and into the report information section.

| Level | Facts | Mandatory | Optional | Human gate |
|---|---|---|---|---|
| `minimal` | `mode in {change, repair, maintenance}`, `risk=low`, `audit=runtime-only`, measured `units_total <= MAX_UNITS_MINIMAL = 5` | coverage manifest, change map, the H42 purpose section, one A1-A8 section per unit, verbatim code blocks, V1-V13 plus V15-V16, offline check, accuracy review | diagrams, related code, glossary | closed by default; opened only on explicit user request |
| `standard` | every other confirmed fact set | all of `minimal`, plus the diagrams required by D1-D6, related-code references (A11), and -- for every unit that declares a `change_class` -- its `REQUIRED_DIMENSIONS` design dimensions (A19, three-state) | glossary, depth blocks (A20) | closed by default; opened only on explicit user request |
| `full` | `risk=high`, or `audit in {result, full}`, or explicit user request | all of `standard`, plus the glossary, per-unit alternative comparison, and the depth blocks (A20) a unit's change class triggers (e.g. `function` -> call relations, `member-var` -> lifecycle, `control-flow`/`signature`/`data-schema` -> before/after) | none | closed by default; opened only on explicit user request |

The `audit` values in this matrix are members of the shipped planning domain
`{runtime-only, result, full, unknown}` (`skills/xc-work/scripts/plan_work_policy.py`), which is
the vocabulary a caller actually supplies. `minimal` selects the lightest audit value,
`runtime-only`; `full` is selected by the two heavier ones, `result` and `full`; `unknown` is
never a reason to lower a tier, because an unknown fact must fail closed to the thicker level.

Three rules constrain the level:

- The level changes content thickness only. All three levels run V1-V13, V15 and V16 **and** the
  accuracy review (V14 at the final stage). `minimal` omits no analysable unit, relaxes no A1-A8
  threshold and skips no hash recomputation or token binding. What `minimal` saves is
  presentation, not proof.
- The gate is not a property of the level. All three levels default to closed; only an
  explicit user request opens it. A `full` report has more content, not more checkpoints.
- The measured unit count can raise the level and never lower it: when `prepare-manifest`
  measures more units than `MAX_UNITS_MINIMAL` while `minimal` was selected, it publishes
  `standard` and records `report.strength_upgrade_reason`.

### Calibration record of the strength constants

The constants that decide and police the tier are mirrored here from the calibration record in
`references/coverage-protocol.md`, because a tier change moves both references. Each value is a
design-stage choice, not a measurement: the repository holds no report corpus, no error budget
and no distribution of `units_total` over real changes, so neither value can be calibrated today.

| Constant | Declared value | Declared in | What it gates | Retention reason |
| --- | --- | --- | --- | --- |
| `STRENGTHS` | `minimal, standard, full` | `build_manifest.py` | the accepted strength vocabulary, the values `report.strength` may take, and the three rows of the matrix above | retained at the design value; three tiers are the smallest set that separates a one-location change from a cross-cutting one, and this tuple is the live enforcement point, so no second copy of the vocabulary is kept anywhere |
| `MAX_UNITS_MINIMAL` | `5` | `build_manifest.py` | the `minimal` tier's unit ceiling and the measured `minimal -> standard` upgrade | retained at the design value; the fuller reason and the calibration procedure are in `references/coverage-protocol.md` |

Any future change to these two values, to the matrix above, or to the unit-window constants
behind them must change this table, the corresponding entry in `references/coverage-protocol.md`
and the boundary test that pins the value **in one change**, so the value, its recorded reason
and its test never drift apart. Inventing a number, or presenting an estimate as a calibrated
result, is excluded.

## Analysis text input

`build_skeleton.py` reads an optional analysis JSON. Every field it does not receive is
rendered as an empty field, which V4 then fails: building a skeleton and validating it are
different steps, and only the validator judges.

```json
{
  "schema_version": 1,
  "language": "en",
  "title": "…", "subtitle": "…",
  "overview": {"what_changed": "…", "why": "…", "impact": "…", "reading_guide": "…"},
  "process_position": {"narrative": "…", "before": "…", "after": "…"},
  "related_code": [{"path": "src/x.py", "lines": "10-20", "note": "…", "code": "…"}],
  "glossary": [{"term": "…", "explanation": "…"}],
  "verification": {"commands": [{"command": "…", "result": "…"}], "residual_risks": "…"},
  "diagrams": [{"id": "diagram-1", "type": "flow", "render_mode": "svg", "…": "…"}],
  "rounds": [{"round": 1, "refresh_reason": "initial", "scope": "…",
              "manifest_sha256": "…", "at": "…", "sections": "…"}],
  "report_info": {"gate_note": "…", "skip_note": "…"},
  "purposes": [{"id": "p1", "title": "…", "theme": "…", "narrative": "…",
                  "unit_refs": [1, 2]}],
  "related_code": [{"path": "src/x.py", "lines": "10-20", "note": "…",
                    "relation_type": "caller", "code": "…"}],
  "units": {"1": {"purpose": {"id": "p1", "title": "…"},
                 "related_code_refs": [{"path": "src/x.py", "lines": "10-20",
                                        "note": "…", "relation_type": "caller", "code": "…"}],
                 "fields": {"what": "…", "why": "…", "design": "…", "tradeoffs": "…",
                             "flow-position": "…", "alternatives": "…",
                             "business-process": "…", "data-and-control": "…"},
                 "change_class": "function",
                 "design_lead": "…",
                 "design_dimensions": [
                     {"key": "role", "answer": "…"},
                     {"key": "before_after", "answer": "…"},
                     {"key": "tradeoffs", "not_applicable": true, "reason": "…"}],
                 "depth_blocks": [
                     {"kind": "call_relations", "unit_label": "fn()",
                      "callers": [{"label": "caller_a", "loc": "src/a.py:10"}],
                      "callees": [{"label": "callee_x", "loc": "src/x.py:5"}]},
                     {"kind": "before_after", "title": "…",
                      "rows": [{"step": "…", "before": "…", "after": "…", "change": "modified"}]},
                     {"kind": "lifecycle", "resource": "self._x", "complete": true,
                      "phases": [{"phase": "init", "loc": "src/a.py:12", "action": "…",
                                  "state": "…", "note": "…"}]}],
                 "covers": ["#unit-1"], "note": "…"}}
}
```

The `change_class`, `design_lead`, `design_dimensions` and `depth_blocks` keys are the optional
analysis-depth layer (A18-A20). A unit that omits them renders and validates exactly as before;
when `change_class` is present, V21 requires the class's `REQUIRED_DIMENSIONS` to be addressed and
V22 checks any depth block's shape and binding.

Round records are mandatory: when the analysis carries none, the builder writes one
`refresh_reason=initial` row, and V5 fails any table whose first row is not `initial`, so
"only one round ran" and "a round record was lost" stay distinguishable.
