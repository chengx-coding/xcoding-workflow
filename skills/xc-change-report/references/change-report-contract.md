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
| H6 | `section-overview` | executive summary: top what/why/impact, the three-answer brief (H50), metadata badges, reading guide |
| **H42** | `section-elements` | the architectural-element layer: the derived element map, the element index, and one six-part profile per element (H49); the optional design topics render here too |
| **H8** | *retired* | `section-process-position` is no longer a section; its narrative is the element section's lead, and the macro before/after is carried by the element profiles |
| H7 | `section-change-map` | the change map and the exclusion table (the scannable index into the detail) |
| H9 | `section-units` | one section per analysable change unit, grouped under its element and folded (D3), including that unit's inline diagrams (FR-VIS-4) |
| H10 | `section-related-code` | unchanged code quoted to explain context |
| H11 | `section-diagrams` | macro / cross-unit diagrams only; the element map and unit-level diagrams are rendered elsewhere (FR-VIS-4, H48) |
| H12 | `section-verification` | referenced verification commands, results, residual risk |
| H13 | `section-glossary` | every proper noun used in the body, explained once |
| H14 | `section-report-info` | generation time, manifest hash, baseline, the baseline capture scope, rounds, skips, degradations, element and bucket counts, and the human-confirmation status |

The visual order is top-down (macro to detail): overview, the element map and profiles, then the
scannable `section-change-map` index, then the per-element unit detail. The H numbers are stable
ids, not positions, and the single source of the physical order is `SECTION_IDS` in
`scripts/build_manifest.py`, which the renderer, the table of contents and V5 all consume.

H6-H12 and H14 are judged mechanically (V5). The completeness of H13 and the writing quality
of H6-H12 are human review items; no script decides whether a term was really explained.

## Change map

- **H15** One row per analysable change unit.
- **H16** Seven columns, in this order: repository-relative path, change kind, element tag,
  unit number, first 12 hex characters of the manifest content hash, code location, link to
  the unit's analysis section. The element tag (A26) is the unit's element id or reserved
  bucket name; a unit with no binding renders an empty tag cell. The code location is
  `<path>:<start>-<end>` taken from `new_range`, or from `old_range` for a unit whose content
  side is the old side (a pure deletion). V5 asserts both the row count and that the
  code-location column is non-empty; V18 asserts the element tag matches the unit's declared
  binding.
- **H17** The change-map row count equals the manifest's `units_total`. Excluded files are
  not counted here and do not appear; the equation performs no subtraction.
- **H18** Excluded entries have their own table with path, category and reason per row, plus
  the totals. Its row count equals `excluded_total + pre_existing_total`. Exclusions are
  never hidden in the manifest only.

## Table of contents and anchors

- **H19** The left sidebar is a fixed three-level table of contents: section, then element
  group, then change unit, collapsible. Section level is always visible; element groups group
  units by element without reordering the globally monotonic unit anchors. V19 asserts every
  unit target exists with no dangling or extra unit; V18 asserts every element entry resolves.
- **H20** Collapsing uses native HTML (`<details>`/`<summary>`) and CSS only. No JavaScript.
- **H21** Every analysable unit has the stable anchor `#unit-<unit_index>`, where
  `<unit_index>` is the manifest's globally monotonic unit number, not a per-file restart and
  not a git hunk number. File-level anchors are `#file-<file-slug>`.
- **H22** `<file-slug>` is built by the script: take the repository-relative path, lowercase
  it, replace `/`, `\`, `.` and every non-alphanumeric character with `-`, then collapse runs
  of `-`. The model never writes an anchor by hand.
- **H23** Cross-references inside the page use in-page anchors. Every unit section carries a
  previous/next change navigation, a breadcrumb and a "back to element" link to its H42 element
  profile (`#element-<element_id>`). prev/next still follow the document order across element
  groups, never truncating at a group boundary. V18 asserts the bidirectional element-to-unit
  and unit-to-element links are not dangling.
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
- **A16** *Retired.* The purpose layer (`analysis.purposes`, a per-unit `purpose` tag and the
  `section-purposes` cards) is replaced by the architectural-element layer (A25-A30). The
  `purposes` key is still tolerated in an analysis JSON so older input loads, but it is never
  rendered and it gates no check.
- **A17** `related_code_refs` lists unchanged code quoted inside the unit as one or more
  `report-code-context` blocks: `{"path", "lines", "note", "relation_type", "code"}`.
  `relation_type` is a closed enumeration `caller | callee | data-structure | contract`.
  These blocks never participate in V10; V20 enforces their `data-path`/`data-lines` and
  relation type.

## Architectural-element layer (A22, A25-A30)

The element layer is the report's spine: it answers "which system element changed, and how did
it work before and after", which neither the whole-change summary nor one diff hunk can answer.
`references/analysis-depth.md` explains how to divide a change into elements; the items below
are the contract increment the scripts enforce.

- **A22** `brief` is the three-answer L1 brief rendered in the overview: `worst_case`,
  `rollback` and `unverified`. It is required at every strength. Each answer is at least
  `MIN_BRIEF_ANSWER_CHARS = 60` non-whitespace characters, the three answers together are
  between `MIN_BRIEF_TOTAL_CHARS = 240` and `MAX_BRIEF_TOTAL_CHARS = 1200`, and no answer may
  be a placeholder. H50 fixes its rendering (`data-brief-part`).
- **A25** `elements` is a list of one to `MAX_ELEMENTS = 7` architectural elements. Every item
  carries the eight profile keys `id`, `name`, `kind`, `role`, `before`, `after`, `why`,
  `contract`; `kind` is a member of `ELEMENT_KINDS` (`component`, `behaviour`, `data`,
  `contract`). An element id is an anchor fragment: no whitespace, quote, angle bracket or `#`.
  An optional `relations` list is A30.
- **A26** Every analysable unit carries `element_ref`: either a declared element id, or one of
  the two reserved buckets `mechanical` and `unassigned`. The unit's `element_ref` is the
  single binding; an element never repeats the unit list, and the renderer derives
  element-to-unit links from it.
- **A27** The `before`, `after`, `why` and `contract` parts are each at least
  `MIN_ELEMENT_PART_CHARS = 60` non-whitespace characters, and `before` and `after` must differ
  after normalisation (lowercase, punctuation and whitespace removed). A rewrite of the same
  sentence is not a before/after comparison.
- **A28** Purely mechanical changes (version strings, formatting, comment spelling) never become
  elements. They bind to `element_ref: "mechanical"`; the count is rendered in the report
  information section.
- **A29** Tests and fixtures never become elements of their own. They bind to the element they
  verify; a test that cannot be attributed uses `element_ref: "unassigned"` and the count is
  rendered in the report information section.
- **A30** `relations` is an optional list of `{"from", "to", "label"}` on an element. `from`
  and `to` must be declared element ids and `label` is the interface or dependency the edge
  carries; the direction reads "`from` requires the interface `label` that `to` provides". The
  builder derives the L1 component map from these relations (D27). A relation naming an
  undeclared element is ignored: the builder never invents a component.

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
- **A20** `depth_blocks` is a list of structured, deterministic blocks, each a
  member of `DEPTH_BLOCK_KINDS` (`before_after`, `lifecycle`, `call_relations`). A `before_after`
  block is a **full-width comparison of steps**: each step is one `report-ba-step` card carrying
  `data-change` from `DEPTH_CHANGE_VOCAB` (`added|removed|modified|unchanged`), with a before panel
  and an after panel that sit side by side on a wide viewport and stack on a narrow one, so long
  prose gets the full content width instead of a crushed table cell. A `lifecycle` block is a phase
  table with a `complete` flag; a `call_relations` block is a `callers | unit | callees` table. Any
  wide table is wrapped in a `report-table-scroll` container so it scrolls locally instead of
  overflowing the page. Every block renders a `report-depth-block` figure carrying `data-unit` and
  `data-kind`. Depth blocks are context: they never participate in V10, add no SVG geometry and no
  golden fixture, and load no external resource. V22 enforces their kind, unit binding and change
  vocabulary (carrier-agnostic: it checks the `data-change` of any element inside a `before_after`
  block, not only a table row).
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
  `report-code-context`, `report-diff-add`, `report-diff-del`, `report-anchor`. The element
  layer (A25-A30) adds `report-meta-badges`, `report-brief`/`report-brief-item` (the A22 brief,
  carrying `data-brief-part`), `report-elements-lead`, `report-element-map` (the derived
  component map's wrapper), `report-element-index` (the element list),
  `report-element`/`report-element-head`/`report-element-anchor`/`report-element-kind`
  (one profile per element, carrying `data-element` and `data-element-kind`),
  `report-element-part` (one per H49 part, carrying `data-element-part`),
  `report-element-tag`/`report-element-badge` (the element tag in the change map and the quick
  index), `report-unit-group`/`report-unit-group-count` (the element grouping of the units),
  `report-unit-detail` (the native `<details>` that folds a unit's detail, D3),
  `report-back-to-element`, `report-element-context`, `report-quick-index`, `report-unit-head`,
  `report-unit-summary`, `report-unit-context` and `report-breadcrumb`. The retired purpose
  classes are no longer emitted. The presentation
  rebuild adds, for readability only, `report-stat-grid`/`report-stat` (the mechanical
  overview key-figure strip), `report-summary-block`/`report-kind-bar`/`report-kind-legend`
  (the mechanical change-kind distribution derived from the manifest), `report-unit-fields`
  (the per-unit field wrapper) and `report-unit-more` (the native `<details>` that folds the
  four secondary A1-A8 fields). The analysis-depth layer (A18-A20) adds `report-change-class`
  (the A18 badge carrying `data-change-class`), `report-design-lead` (the L1 lead rendered
  before the code block), `report-design-dimensions`/`report-design-dimension`/
  `report-dimension-na` (the A19 dimensions, carrying `data-dimension`), and
  `report-depth-block`/`report-depth-table`/`report-callgraph`/`report-lifecycle-flag` (the A20
  structured blocks, carrying `data-unit` and `data-kind`), the before/after comparison classes
  `report-ba-steps`/`report-ba-step`/`report-ba-step-head`/`report-ba-step-name`/`report-ba-change`/
  `report-ba-panels`/`report-ba-panel`/`report-ba-before`/`report-ba-after`/`report-ba-label` (each
  step carrying `data-change`), the `report-table-scroll` wrapper that keeps any wide table from
  overflowing the page, the `report-code-head`/`report-code-lang` code-block header, and the
  `report-unit-diagram` wrapper that carries a unit-level diagram rendered inline inside its unit
  block (FR-VIS-4). The depth
  classes carry no `report-code` and never enter the V10 recomputation. These carry no analysis content of their
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
- **H39** The single owner of the shared writing method is the public `xc-writing`
  Skill. The public `xc-document` "Default Human-Readable Authoring" contract remains the
  compatible entry: it maps the writing task, evidence, audience, fixed language, and explicit
  requirements to that method. This Skill cites the public entry rather than restating the
  method; report-specific additions remain below.
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

## Optional design-topic layer

- **H43** `analysis.design` is optional. Its absence is the legacy path and does not change the
  fixed section order, minimal strength, or V17-V37 behavior. When present, it is rendered inside
  H42 (`section-elements`) after the element profiles, as the decision record of the element
  map; it never creates a second top-level report or a second macro before/after narrative.
- **H44** The `overview` fields and the element profiles remain the sole macro narrative
  authority. A design topic may link to those rendered anchors and add a concise decision or
  boundary, but it must not require authors to repeat the overview fields.
- **H45** A topic has a unique `id`, visible non-empty `title` and `summary`, a display-only
  `kind` (`behavior`, `architecture`, `data`, `state`, `tradeoff`, or `risk`), optional
  `current`/`target`/`decision`, and optional `element_refs`, `unit_refs`, `diagram_refs` and
  `evidence`. `behavior`, `architecture`, `data` and `state` topics require current and target;
  tradeoff and risk topics may omit them only with a visible reason. `purpose_refs` is retired
  with the purpose layer (A16); a topic that still carries it must move those references to
  `element_refs`.
- **H46** Topic `unit_refs` are the only author source for topic-to-unit relations. The builder
  derives unit-to-topic backlinks and the topic index; an analysable unit may link to multiple
  topics without duplicating its code or analysis.
- **H47** Evidence refs are typed, non-empty in-page anchors. `intent` accepts
  `approved|planned|unknown`, `implementation` accepts `observed|planned|unknown`,
  `verification` accepts `passed|planned|unknown`, and `inference` accepts `unknown|planned`.
  Planned, unknown and inference evidence carries a visible reason. A filename or bare source
  range is not an evidence closure.
- **H48** Diagram rendering has one canonical owner (`topic`, `unit`, `element-map`, or `macro`)
  and exactly one `<figure>`, while references may be many-to-many and render backlinks only. The
  materialized diagram registry includes author and derived unit diagrams, so a topic may
  reference a derived id without copying its specification. The derived element map renders
  inside H42 and is never rendered a second time in H11.
- **H49** Each element profile renders its six parts as `data-element-part` blocks in the fixed
  order `what/role`, `before`, `after`, `why`, `contract`, `refs`. V35 checks the order and V17
  checks presence.
- **H50** The overview renders the A22 brief as three `data-brief-part` blocks
  (`worst_case`, `rollback`, `unverified`), each with a visible answer; V37 checks the content
  thresholds.

## Element-layer and analysis-depth validation

- **V17** Element profile completeness (A25/H49): H42 renders at least one
  `report-element`; every profile has a visible name, a legal `data-element-kind`, all six
  `data-element-part` blocks and non-empty text in each, and its `refs` part links at least one
  real analysable unit.
- **V18** Element cross-reference closure: the change-map element cell for each unit equals the
  unit section's `data-element`; every element profile's unit links are units that declare that
  element; every unit that declares an element (outside the reserved buckets) finds a rendered
  profile; the back-to-element links and the table-of-contents element entries are not
  dangling; and the related-code links are not dangling.
- **V19** Three-level TOC completeness: every section, element group and unit target in the
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
  `DEPTH_BLOCK_KINDS` and a `data-unit` naming an analysable unit; inside a `before_after` block
  every element that carries `data-change` (a `report-ba-step` card) has a value in
  `DEPTH_CHANGE_VOCAB` -- the check is carrier-agnostic and does not require a table row; depth
  blocks are excluded from the V10 recomputation selection. Renders-nothing units stay vacuous.

- **V23** Near-content diagram placement (FR-VIS-4): a diagram whose spec id ends in `-unit-<N>`
  (a call graph or before/after flow derived from unit N's depth blocks, D21) must render inline
  inside that unit's `#unit-<N>` block, and must not sit in the macro `section-diagrams` region;
  the macro region carries only macro / cross-unit diagrams. The rule keys on the figure id, so it
  is independent of the page-wide `diagram-spec-N` numbering and of V8 (which matches a spec to its
  figure by id anywhere on the page). Whether a diagram is appropriate at all stays a human /
  accuracy judgement; V23 only proves placement.

- **V24** Design-topic shape: when `analysis.design` is present, every topic has a unique valid
  id, a visible title and summary, a supported display kind, and the required current/target
  fields for its kind. Minimal reports without design remain valid without this check.
- **V25** Design reference closure: element, unit, diagram and evidence refs resolve to rendered
  in-page anchors or the materialized diagram registry. Evidence kind/status combinations follow
  H47, and planned/unknown/inference entries carry a visible reason.
- **V26** Design navigation and ownership: every topic appears in the design index, every topic
  unit ref has a generated unit backlink, every canonical figure renders once, and shared refs do
  not duplicate figures. Unclaimed macro figures remain in H11; unit-derived figures remain in
  their unit block.
- **V27** Design accuracy coverage: the final accuracy artifact may include `topic_findings[]`.
  Required topic findings (wrong or misleading topic/diagram/evidence claims) set the existing
  accuracy-open flag and enter the same bounded revision loop as unit findings. Per-unit V14
  coverage remains unchanged.

- **V33** Element identity and count (A25): the report renders between `MIN_ELEMENTS = 1` and
  `MAX_ELEMENTS = 7` element profiles; every id is unique and usable as an anchor fragment;
  every `kind` is a member of `ELEMENT_KINDS`; and the element count rendered in the report
  information section equals the number of profiles.
- **V34** Unit-to-element closure (A26/A28/A29): every analysable manifest unit has a section
  carrying a non-empty `data-element`; a value is either a rendered element id or one of the
  reserved buckets; and the mechanical and unassigned counts in the report information section
  equal the units that declare those buckets. An unbound unit fails.
- **V35** Reading order (H49): `section-elements` renders before `section-units`, and every
  element profile renders its six parts in the fixed order `role, before, after, why, contract,
  refs`. Presence is V17's job; this check owns the order.
- **V36** Before/after quality (A27): `before`, `after`, `why` and `contract` each carry at
  least `MIN_ELEMENT_PART_CHARS = 60` non-whitespace characters, and `before` and `after`
  differ after normalisation (lowercase, punctuation and whitespace removed). The check proves
  a contrast exists, never that it is correct.
- **V37** Brief completeness (A22/H50): the overview renders all three `data-brief-part`
  answers; each carries at least `MIN_BRIEF_ANSWER_CHARS = 60` non-whitespace characters, the
  three together stay between `MIN_BRIEF_TOTAL_CHARS = 240` and `MAX_BRIEF_TOTAL_CHARS = 1200`,
  and no answer is a placeholder.
- **V14** also accepts an optional `element_findings[]` in the accuracy artifact: a finding
  names a rendered element id, carries a verdict from `VERDICTS`, requires a reason when the
  verdict is `wrong` or `misleading`, and a non-accurate element finding sets
  `report.accuracy_open_issues` exactly like a unit or topic finding.

## Strength matrix

The level is fixed by confirmed facts, never by task length or wording, and is written to
`report.strength` and into the report information section.

| Level | Facts | Mandatory | Optional | Human gate |
|---|---|---|---|---|
| `minimal` | `mode in {change, repair, maintenance}`, `risk=low`, `audit=runtime-only`, measured `units_total <= MAX_UNITS_MINIMAL = 5` | coverage manifest, change map, the H42 element section and its profiles, the A22 brief, one A1-A8 section per unit, verbatim code blocks, V1-V18 plus V33-V37, offline check, accuracy review | diagrams, related code, glossary | closed by default; opened only on explicit user request |
| `standard` | every other confirmed fact set | all of `minimal`, plus the diagrams required by D1-D6, the component element map (D27), related-code references (A11), and -- for every unit that declares a `change_class` -- its `REQUIRED_DIMENSIONS` design dimensions (A19, three-state) | glossary, depth blocks (A20) | closed by default; opened only on explicit user request |
| `full` | `risk=high`, or `audit in {result, full}`, or explicit user request | all of `standard`, plus the glossary, per-unit alternative comparison, and the depth blocks (A20) a unit's change class triggers (e.g. `function` -> call relations, `member-var` -> lifecycle, `control-flow`/`signature`/`data-schema` -> before/after) | none | closed by default; opened only on explicit user request |

The design-topic layer is optional at every level. A minimal report never requires it. When a
standard or full author supplies it to answer a real reader question, V24-V27 apply; the level
does not impose a fixed topic count, chart count, or prose length. This keeps the existing
minimal burden while allowing a full report to explain design decisions before unit detail.

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
  "brief": {"worst_case": "…", "rollback": "…", "unverified": "…"},
  "process_position": {"narrative": "…"},
  "design": {"topics": [{"id": "grant-path", "title": "…", "kind": "behavior",
               "summary": "…", "current": "…", "target": "…", "decision": "…",
               "element_refs": ["e1"], "unit_refs": [1],
               "diagram_refs": ["diagram-1"],
               "evidence": [{"kind": "implementation", "status": "observed",
                              "ref": "#unit-1"}]}]},
  "related_code": [{"path": "src/x.py", "lines": "10-20", "note": "…", "code": "…"}],
  "glossary": [{"term": "…", "explanation": "…"}],
  "verification": {"commands": [{"command": "…", "result": "…"}], "residual_risks": "…"},
  "diagrams": [{"id": "diagram-1", "type": "flow", "render_mode": "svg", "…": "…"}],
  "rounds": [{"round": 1, "refresh_reason": "initial", "scope": "…",
              "manifest_sha256": "…", "at": "…", "sections": "…"}],
  "report_info": {"gate_note": "…", "skip_note": "…", "human_confirmation": "none"},
  "elements": [{"id": "e1", "name": "Task dispatch", "kind": "behaviour",
                 "role": "…", "before": "…", "after": "…", "why": "…", "contract": "…",
                 "relations": [{"from": "e1", "to": "e2", "label": "IBaseline"}]}],
  "related_code": [{"path": "src/x.py", "lines": "10-20", "note": "…",
                    "relation_type": "caller", "code": "…"}],
  "units": {"1": {"element_ref": "e1",
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
