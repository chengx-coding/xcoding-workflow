# Analysis Depth Methodology

This reference is normative for the **analysis-depth layer** of the change report: the change
taxonomy a unit may declare (A18), the design dimensions each class must address (A19), and the
structured depth blocks a unit may carry (A20). It exists so a reader can understand a change
**top-down, from design intent to concrete implementation** — not just read the diff.

The machine-readable sources of truth are the constants in `scripts/build_manifest.py`:
`CHANGE_CLASSES` (A18), `DIMENSION_LABELS` and `REQUIRED_DIMENSIONS`/`REQUIRED_DIMENSIONS_DEFAULT`
(A19), `MIN_DIMENSION_CHARS`, `MIN_NA_REASON_CHARS`, `DEPTH_BLOCK_KINDS` and
`DEPTH_CHANGE_VOCAB` (A20). This document explains and enumerates; those constants enforce.

## Why this layer exists

The eight per-unit fields (A1-A8) prove that *some* analysis exists and is bound to the code
(V4/V10/V11). They do not make the analysis **answer the design questions a reviewer actually
asks**: what role does this play, what was the flow before and after, why this approach and not
another, what is the lifecycle, who calls it and what does it call. Industry practice converges
on the same answer set:

- An **ADR** records Context, the Decision (active voice, "we will…"), the **Alternatives
  considered and why they were rejected**, and the **Consequences including the negative ones**.
- A **design doc / RFC** states Goals and Non-Goals, then explains guide-level (intent) before
  reference-level (detail) — a top-down order.
- **Google's code-review guidance** ranks **design** highest and asks reviewers to weigh
  complexity/over-engineering, tests, naming, and comments that explain *why* not *what*.
- **SemVer / deprecation** frame compatibility, lifecycle, and migration.
- **C4** and **literate programming** give the layering: macro context → structure → code, one
  abstraction level at a time, in human-reading order.

The report turns that consensus into a per-unit, per-change-class checklist.

## The six-layer skeleton (every change answers these)

Every analysable change, regardless of class, is explained across six layers. The class-specific
`REQUIRED_DIMENSIONS` below are the emphasis a class adds on top of this shared skeleton.

| Layer | Question | Dimension key(s) |
|---|---|---|
| L1 Context | Where does this sit and what is its job? | `role` |
| L2 Before/After | What was the behaviour/structure before, and after? | `before_after` |
| L3 Motivation | Why is the change needed; what if it were skipped? | `motivation` |
| L4 Trade-offs / Alternatives | What else was considered and why was it rejected; what does this cost? | `alternatives`, `tradeoffs` |
| L5 Impact | Who is affected: callers/callees, compatibility, side effects, error paths, performance? | `upstream_downstream`, `impact_risk` |
| L6 Verification | How is the new behaviour proven correct and the old behaviour preserved? | (covered by A1-A8 and the verification section) |

`lifecycle` is a seventh, cross-cutting dimension used where a value or resource has a birth and
death worth tracing (see the state/data classes).

## A18 - The change taxonomy

`change_class` is optional. When a unit declares one it MUST be a member of `CHANGE_CLASSES`, and
the report renders a `report-change-class` badge in the unit head. A unit with no class leaves
V21 vacuous, so analysis written before this layer still validates.

The classes group into three families. For each class the table gives its focus, the dimensions
it must address (the `REQUIRED_DIMENSIONS` entry), and the depth block that best carries it.

### State / data classes

| Class | Must address (beyond the skeleton) | Best depth block |
|---|---|---|
| `member-var` | why a field and not a parameter / local / derived value / injected collaborator; **lifecycle** (declare → init → assign → read → dispose; per-request vs long-lived); who writes and who reads; the invariant it shares with other fields | `lifecycle` |
| `constant-config` | why named rather than a magic value; for an enum, whether every exhaustive switch was updated and the ordinal-vs-name risk; for config, load time, precedence, and fail-fast vs silent default | before/after or a value table |
| `data-schema` | breaking or not; the Expand→migrate→Contract path; serialization compatibility (never reuse a field number; BACKWARD/FORWARD/FULL); producers/consumers and the required compatibility direction; backfill and rollback safety | `before_after` (field-level) |
| `global-state` | why global rather than an instance field or an injected singleton; the hidden dependencies made explicit (who reads/writes); test isolation and initialization thread-safety | `call_relations` or a read/write table |

### Behaviour / control-flow classes

| Class | Must address | Best depth block |
|---|---|---|
| `function` | single responsibility and the flow it is triggered in; **old flow vs new flow**; **upstream callers and downstream callees**; why this shape and its trade-offs | `call_relations`; `before_after` for the flow |
| `signature` | the exact before→after of the signature; compatibility class (added-optional vs added-required/removed/reordered/retyped/return-changed); how many callers change and their migration | `before_after`; caller table |
| `control-flow` | old vs new control flow; which cases the new branch covers and which it omits; guard/early-return state consistency; loop/recursion termination | `before_after` (step table) |
| `call-dependency` | the before/after dependency topology; whether the direction violates layering or introduces a cycle; the new failure modes a new dependency brings | `call_relations` |

### Structure / contract / systemic classes

| Class | Must address | Best depth block |
|---|---|---|
| `type-contract` | is-a (inheritance) vs has-a (composition) and why; the contract method-set diff; whether LSP still holds; fragile-base-class risk | before/after (member diff) |
| `api-contract` | compatibility level (SemVer); field-level contract diff; the deprecation stage and migration path; the consumer list and old-client failure modes | `before_after`; version state |
| `concurrency` | the shared mutable state and its guarding lock; atomicity of check-then-act / read-modify-write; happens-before visibility; deadlock (unified lock order) and illegal/unreachable states — **failure modes must be explicit** | `before_after`; a lock-order table |
| `error-handling` | exception vs result; the error-set diff; validation tightened/loosened; timeout/retry parameters; resource release on the error path; retry side effects (idempotency) | error-code table; `before_after` |
| `di-lifecycle` | the binding diff and scope (singleton/scoped/transient); captive-dependency risk (a scoped object captured by a singleton); init order and cycles | `lifecycle`; dependency table |
| `performance` | the measured bottleneck this targets (avoid premature optimization); the complexity diff; the benchmark in a reproducible environment; cache invalidation/penetration risks; any consistency-semantics change | benchmark table; `before_after` |
| `refactor` | name the Fowler catalogue move (Extract/Move/Rename/Inline…); **prove external behaviour is unchanged** (tests green, no contract change); reference integrity (all references updated); public-symbol renames trigger deprecation | `before_after` (element move map) |
| `test-config` | which behaviour a test protects and whether it ships with that behaviour; flakiness; reproducible-build impact; secrets never logged | config-diff table |
| `other` | the shared skeleton (`role`, `motivation`, `impact_risk`) | any |

## A19 - Design dimensions and the three-state answer

Each dimension a class requires is answered in one of exactly three states. This is the rule that
makes "address it" checkable without judging correctness:

1. **Answered** — a `report-design-dimension` block whose text clears `MIN_DIMENSION_CHARS`
   non-whitespace characters.
2. **Not applicable, with a reason** — the block is marked not-applicable and carries a reason of
   at least `MIN_NA_REASON_CHARS` characters. A high-risk dimension (concurrency, serialization
   compatibility, migration rollback, test isolation) can be waived only with a stated reason,
   never silently.
3. **Missing** — the block is absent. V21 fails a *required* dimension that is missing.

V21 checks presence and the three-state discipline. It does **not** judge whether the answer is
true; that is the accuracy review's job (V14) and, when open, the human gate's. Keep the two
strictly separate: "the dimension was addressed" and "the answer is correct" are different claims.

The dimension keys and their report headings are `DIMENSION_LABELS`. The design lead (L1) is
rendered *before* the code block; the remaining dimensions render *after* it, so the reader meets
intent, then code, then the fuller design analysis — the top-down order C4 and literate
programming prescribe.

## A20 - Structured depth blocks

Depth blocks carry the relations that prose states poorly. All three are **deterministic HTML
tables**: they add no SVG geometry and no golden fixture, they load no external resource, they
run no script, and they never participate in the V10 recomputation (they are context, like
`report-code-context`). Each binds to its unit through `data-unit` and declares a `data-kind` in
`DEPTH_BLOCK_KINDS`.

- **`before_after`** — a step table with `before`, `after`, and a `change` column drawn from
  `DEPTH_CHANGE_VOCAB` (`added|removed|modified|unchanged`). Use it for old-flow-vs-new-flow, a
  signature diff, a schema field diff, or a control-flow path diff. The change value is
  triple-encoded (column text + row `data-change` + styling) so it does not rely on colour alone.
- **`lifecycle`** — a phase table (`declare → init → assign → read → dispose`) with a
  `file:line` location per phase and a `complete` flag: a resource that is initialised but never
  released renders `complete=false`, which is exactly the leak signal a reviewer wants. Use it for
  member variables, resources, locks, connections, and DI scopes.
- **`call_relations`** — a three-column table `callers (upstream) | unit | callees
  (downstream)`, each side listing `label` + `file:line`. Use it for a new/changed function or a
  changed call dependency, to show who depends on the unit and what the unit now depends on.

### Tables and their derived diagrams

The three depth blocks are stored as deterministic HTML tables (ordered, enumerable,
row-diffable, accessible without extra markup). Following the prefer-diagrams principle (A21),
two of them also **derive a diagram automatically** and render it beside the table (D21): a
`call_relations` block derives a layered call-graph SVG, and a `before_after` block derives a
paired before/after flow SVG. The derivation reuses the `flow` carrier, is a pure function, and
is re-rendered and checked by V8 like any flow spec; it is on at `standard`/`full`, skipped at
`minimal`, and a block opts out with `derive_diagram: false`. So the reader gets the table for
completeness and the diagram for intuition, from one piece of authored data.

## Prefer-diagrams: suitability by change class (A21 / D20)

When the information content is comparable, a diagram is the more readable expression. The map
below is the authoring/review guidance and the basis of the non-blocking D20 advisory: a unit of a
diagram-preferred class that provides no diagram and does not waive the diagram-relevant
dimensions earns an advisory (never a failure). Light classes may omit a diagram.

| change_class | best expression | preferred diagram (carrier) |
|---|---|---|
| `function` (multi-step or cross-module) | diagram | call graph (flow SVG, derived) + before/after flow (flow SVG, derived); sequence (D22 SVG) for timed interaction |
| `call-dependency` | diagram | call/dependency graph (flow SVG, derived from `call_relations`) |
| `control-flow` | diagram | before/after flow comparison (flow SVG, derived from `before_after`) |
| `concurrency` / state field | diagram | state machine (state SVG); sequence (D22 SVG) for interaction timing |
| `data-schema` | diagram | ER (table carrier) + field before/after (`before_after`, derived flow) |
| `type-contract` | diagram | class relations (table carrier) |
| `api-contract` | diagram or table | sequence (D22 SVG or table) + field before/after |
| `signature` | diagram or table | signature before/after (table) + affected-caller graph (flow SVG) |
| `member-var` / `global-state` | mixed | lifecycle (table) + read/write or call graph (flow SVG) |
| `constant-config` / `test-config` / `other` (light) | may omit | none required (D6); no advisory |

The carrier choice follows the deterministic-rendering rule: an ordered, enumerable, row-diffable
relation (class members, ER fields) stays a table; a two-dimensional topology (a call graph, a
flow, a state machine) is a layered SVG; a timed interaction may use the optional sequence SVG
(D22). `class` and `er` keep the table carrier because a deterministic, non-overlapping SVG layout
for them is not guaranteed and a low-quality SVG is not accepted (D18) - that is a documented
boundary, not an oversight.

## Strength matrix interaction

The analysis-depth layer thickens content; it changes no mechanical check.

- `minimal` — does not require `change_class`, `design_dimensions`, or `depth_blocks`.
- `standard` — a unit that declares a `change_class` must address that class's
  `REQUIRED_DIMENSIONS` (three-state).
- `full` — additionally provides the depth blocks a class's changes trigger (a `function`'s call
  relations, a `member-var`'s lifecycle, a `control-flow`/`data-schema`/`signature` before/after)
  and the alternatives dimension.

## Honest capability boundary

State these limits wherever the analysis-depth guarantees are described; do not soften them.

- V21 proves that each required design dimension was **addressed** (answered to the length floor
  or waived with a reason). V22 proves each depth block is **well-formed and bound** to its unit.
  Neither proves the answer or the diagram is **correct** or **complete about the real design**.
- "This lifecycle is actually complete", "this before/after really matches the code", "these are
  really all the callers" are judgements for the accuracy review worker, and for the human gate
  when it is open. A worker can still judge wrongly; the mechanism moves the residual risk from
  "nobody checked" to "somebody checked and may still be wrong". It does not reach zero.
- The change class is author-declared. The report does not infer it from the diff, so a
  mis-declared class is a content error the accuracy review must catch, not a mechanical one.

## References

The methodology above is distilled from: Architecture Decision Records (Nygard; MADR); Google
*Design Docs* and the Rust RFC template (Goals/Non-Goals, guide- vs reference-level, alternatives,
drawbacks); Google engineering practices *What to look for in a code review*; SmartBear peer
review guidance (small change sets); Conventional Commits and Keep a Changelog (change type,
breaking flag, human-facing impact); Semantic Versioning and API deprecation practice
(Deprecate → Sunset → Retire, migration guides); the C4 model (layered abstraction, one level per
view); Knuth's literate programming (human-reading order); Martin Fowler's *Refactoring* catalogue
(named moves, behaviour-preserving); *Java Concurrency in Practice* (check-then-act,
happens-before, unified lock order); and schema-evolution practice (Expand-Contract / Parallel
Change; Protobuf/Avro compatibility rules).
