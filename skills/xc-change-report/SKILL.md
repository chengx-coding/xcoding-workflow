---
name: "xc-change-report"
description: "Produces the single-file human-readable change report for a work order's code change set: a coverage manifest proven against the real worktree, a self-contained HTML report with per-unit analysis bound to the code it explains, and a deterministic validator. Invoke after verification and before the result document when a work order changed analysable code."
---

# XC Change Report

`xc-change-report` turns a work order's code change set into two artefacts a human can
use to review the change without opening an IDE:

- `change-report.html` - one self-contained file, opened by double-clicking it.
- `change-report-manifest.json` - the machine-generated coverage manifest that the report
  is validated against.

A third file, `change-report-verdicts.json`, is produced by the accuracy review worker and
consumed by the validator.

The division of labour is fixed: **scripts build the skeleton and the proof, the model
writes the explanation.** Section order, table rows, anchors, code blocks and diagram
rendering are mechanical and script-generated; the prose of each analysis field is written
by the author and bound to the code by recomputation.

## Element layer

The report's spine is the architectural element: one to seven elements, each with a six-part
profile (`role`, `before`, `after`, `why`, `contract`, `refs`), an element map derived from the
elements' declared relations, and every analysable unit bound to an element or to the explicit
`mechanical`/`unassigned` bucket. The overview carries a three-answer brief (worst case,
rollback, unverified). Hunk-level units stay the analysis unit and the coverage proof, but they
are grouped under their element and folded as the detail layer.

## Optional design-to-implementation layer

An analysis may provide `design.topics` when a change has a real decision-level question that is
hard to understand from the overview, the element profiles and the unit sections alone. Topics
are rendered inside `section-elements` and link to existing element, unit, diagram, and
verification anchors. They do not replace the element profiles, create a second report, or
require a fixed number of charts. Minimal reports remain valid without design.

Design evidence uses typed in-page refs: intent (`approved|planned|unknown`), implementation
(`observed|planned|unknown`), verification (`passed|planned|unknown`), and inference
(`unknown|planned`). Planned, unknown, and inference entries include a visible reason. A figure
has one canonical render owner, but multiple topics may reference it and receive backlinks. Macro
figures remain in `section-diagrams`; derived unit diagrams remain inside their unit. The final
accuracy review grades topic claims, diagram semantics, and evidence status in addition to the
existing per-unit verdicts.

## Position in the lifecycle

- **Measure before reading the contracts.** The group's first step is
  `build_manifest.py`, which is cheap and decides whether there is anything to report at all:
  when it measures zero analysable change units it publishes `run_required=false`, the group
  ends there, and the caller records `work_order.report_skip_reason=zero_analyzable_units`.
  The three normative contracts below run to roughly 17,600 words, so reading them first and
  only then learning that no report is due is wasted work. This ordering matters only for the
  zero-unit case; a group that does produce a report still needs the contracts in full, and
  their density is deliberate rather than excess.
- In the full lifecycle the report group sits between the verification group and the result
  document: only after the code is implemented and verified does the report describe a state
  that still exists. It is the **last group before the result document**, and that lifecycle
  mounts no top-level review node; a review a bridge or an approved solution requires is extra
  work inside the implementation path, so it happens before the report and never between the
  report and the result document.
- On the adaptive path the order is main-session policy, and there the report node is placed
  before an independent review leaf, so the reviewer reads the report. `references/coverage-protocol.md`
  **O9** is the one normative ordering statement for both paths; where this page and O9 could be
  read differently, O9 decides.
- When a review or a gate causes code rework, the report is refreshed by re-running the same
  group; no second report file and no new node type is created.
- Staleness is a refresh edge, not a node failure. Every other validation failure is a node
  failure and is never downgraded to a warning.
- The gate sits inside the refresh pass, so it re-opens in every round and the human always
  reads the refreshed report. A gate decision of `revision-required` or `rejected` selects the
  recovery group in the same round and the pass re-enters, so the reworked report is judged at
  the gate again rather than being closed unreviewed.
- `report.gate_rework_required` has exactly one writer per round and never two. `validate-final`
  writes the value that ends the pass: `true` when it judges the report stale, `false` when it
  judges it fresh. `report-gate` adds the single `true` that a reworking decision carries back to
  the next pass, and the round that write terminates is deliberately the one round with no reset,
  because that `true` is the loop's continue edge. The gate never writes `false` and the recovery
  group never writes the key at all.

The topology that makes that work is fixed: `report-gate` and `report-gate-recovery-group` are
children of `report-pass-loop`, in that order, and `validate-final` follows them with the guard
`report.gate_recovery_required == false`. A gate placed outside the loop cannot re-open on the
refreshed report; a recovery group outside the loop runs after the pass has ended, so its rework is
never judged again; and a recovery group that reset `report.gate_rework_required` would end the
pass before the re-gate.

The report group never edits code. "The code must change" flows back through the normal
implementation path, and the rework segment must be followed by the refresh sequence
(manifest, report, validation) because the covered paths changed.

## Parameters

- `report_path` - `path`; required
  - Scope: `<workbench>/artifacts/<report-node-id>/change-report.html`. The two
    placeholders come from engine return values; never join them by hand.
- `manifest_path` - `path`; required
  - Scope: `change-report-manifest.json` in the same directory.
- `verdicts_path` - `path`; required at the final validation stage
  - Scope: `change-report-verdicts.json` in the same directory.
- `repo_path` - `path`; required
  - Scope: the project repository root the change set is enumerated from.
- `baseline_commit` - `string`; required
  - Scope: the commit recorded once when the work order opened.
- `baseline_worktree_dir`, `baseline_untracked_dir` - `path`; required in practice
  - Scope: the opening worktree snapshot and the untracked-file snapshot under the
    workbench `tmp/` directory. The worktree snapshot holds only the dirty-at-open tracked
    paths, so together with the baseline commit it is what makes pre-existing edits separable;
    the untracked snapshot is what keeps a deletion of a never-tracked file recomputable.
- `language` - `string`; required
  - Scope: `work_order.document_language`. It is the language of the report body; code,
    paths, identifiers, commands and machine output stay verbatim.
- `strength` - `enum`; required
  - Allowed values: `minimal`, `standard`, `full`.
  - Scope: content thickness only. All three levels run every mechanical check and the
    accuracy review.
- `gate_required` - `boolean`; the tree declares `false`, and the caller publishes the value
  - Scope: opens the optional human gate. It is not a property of the strength level. The
    declared `false` is a starting value on a tree that declares the key, never a fallback for a
    caller that omits it: an unwritten key is absent, the gate's guard resolves false, and the
    gate is skipped.
- `stage` - `enum`; required for validation
  - Allowed values: `coverage`, `final`.
  - Scope: `coverage` runs V1-V13, V15 and V16; `final` runs the same set and additionally
    recomputes V14, the accuracy verdicts, because the verdict file does not exist yet at
    coverage time.

## Commands

Run each script from the Skill package; scripts resolve their own package location and never
take a script path from the caller.

```text
python scripts/capture_baseline.py --repo R --workbench W --work-order-id I
       [--baseline-worktree-dir T] [--baseline-untracked-dir U] [--format json|keys]
       [--full-tracked-mirror --consent-reference REF]
python scripts/capture_baseline.py --verify-existing --repo R --workbench W --work-order-id I
       [--baseline-worktree-dir T] [--baseline-untracked-dir U] [--format json|keys]

python scripts/build_manifest.py --repo R --work-order-id W --baseline-commit C
       [--baseline-digest D] --baseline-worktree-dir T --baseline-untracked-dir U
       [--strength minimal|standard|full] [--generated-at TS] --tmp-dir <workbench>/tmp
       --out change-report-manifest.json

python scripts/build_skeleton.py --repo R --manifest change-report-manifest.json
       [--analysis analysis.json] --generated-at TS --tmp-dir <workbench>/tmp
       --out change-report.html

python scripts/validate_report.py --report change-report.html --manifest change-report-manifest.json
       --repo R --work-order-id W --stage coverage|final
       [--verdicts change-report-verdicts.json] [--accuracy-open-issues true|false]
       [--flow-spec ...] [--golden-dir ...]

python scripts/highlight_code.py --language python --file src/app.py
python scripts/render_diagram.py --spec diagram.json --out diagram.html
```

`capture_baseline.py` runs **once**, when the work order opens and before the first mutating
leaf. Its capture form mirrors only what version control cannot reproduce: the tracked paths
whose worktree bytes differ from the recorded baseline commit's bytes (the **dirty-at-open**
set) into `--baseline-worktree-dir` (default `<workbench>/tmp/baseline-worktree`), and the paths
that were untracked at open into `--baseline-untracked-dir` (default
`<workbench>/tmp/baseline-untracked`). A clean tracked path is **not copied**: its open bytes are
its committed bytes, so the baseline commit already holds them. A tracked path **absent** from
the worktree at open, and a tracked path whose bytes exist but cannot be opened, are recorded as
names, because a byte-less path is a fact and not a missing byte; neither contributes a record to
the digest. It then writes the open-state record `<workbench>/tmp/baseline-open-state.json`;
`--format keys` prints the publishable blackboard lines. The published digest keeps exactly its
old value semantics - one `sha256(path-nul-contenthash-lf/v1)` digest over the open-state bytes of
every tracked path that had any - so a previously recorded work order stays valid; only the
recomputation source is hybrid, and the digest's input set and each path's byte source are one
shared definition that the capture, its verification mode, the manifest and the validator all
read.

The record carries the facts no later step can recover, and each exists because a defect could
not be named without it: `untracked_paths`, the names that were untracked at open, so a path that
was untracked at open and has since left the worktree can still be named by
`untracked_snapshot_path_lost:`; `index_modes`, the index mode of every path at open, which is
the only evidence that separates a mode-only change made before the open from one made after it;
`degradations`, the names of the tracked and untracked paths the capture could not open, which
are skipped and named rather than blocking the work order at open; and the frozen capture scope,
`dirty_paths` (the mirror's expected contents) and `deleted_paths` (the tracked paths that were
absent at open). The scope is what keeps "clean at open" distinguishable from "the mirror was
pruned", and it is what lets a later step recompute the digest from the snapshot plus the commit
instead of assuming the snapshot mirrors every tracked path. That is an
addition to the record's schema, not a replacement of it: the thirteen core fields remain the
required set, the added facts stay optional, a record that carries only the core set still loads
and still verifies, and such a record is read as an **unpruned** capture (scope `full`).

Its `--verify-existing` form re-materialises nothing: it recomputes the C4 digest from the
recorded scope - snapshot bytes for a dirty path, baseline-commit blobs for a clean path, and no
record at all for a path the record names as absent or unopenable at open - compares it with the
record's `expected_digest` selected by `--work-order-id`, and fails closed
when they differ, when the record is missing (`baseline_record_missing`) or when the record does
not carry that work order id (`baseline_record_unselected`). A record that holds no commit (the
consent-carrying full copy) is verified from its own snapshot and consults no version control.
Both directory parameters are the two snapshot parameters this package declares, and they are
what C4b and C4a fix.

Where no version control can supply the baseline side - it is not a worktree, `HEAD` does not
resolve, or it resolves to a commit this tool cannot read - the capture **fails closed**: it
copies nothing and exits with the named error `baseline_vcs_unavailable`, carrying the underlying
version-control reason. The single authorisation for a full tracked-set mirror is
`--full-tracked-mirror` together with a non-empty `--consent-reference` naming the explicit user
decision it carries; without both, nothing is copied. No configuration file, key or environment
variable takes part, and the reference is recorded in the open-state record so a reviewer reads
what authorised the copy. That record's limit is stated where the option is offered: it is a
content mirror for a tree with no baseline commit, so `--verify-existing` reproduces its digest
but no validated change report can be produced from it.

`--tmp-dir` is the workbench `tmp/` directory and H4/C37 require it: the baseline snapshots,
the C37 `O`/`B`/`H` no-index scratch files and the skeleton's intermediate diff inputs must all
land there, never in the OS temp directory. `build_manifest.py` and `build_skeleton.py` accept
it and fall back to the OS temp directory only when the caller omits it; a caller that omits it
violates H4/C37. The snapshots carry their own two parameters instead, and their default
locations are the workbench paths C4a/C4b fix: `build_manifest.py` resolves both of them from
the two snapshot paths this work order's open-state record holds when either flag is omitted,
so a caller that names the workbench is never left without the `B` side of the alignment.
That default is a repair, not a licence to omit the flags: a run with neither flag nor a usable
record reads the worktree snapshot as `absent`, degrades every path's provenance and charges the
entire change set to `pre_existing`, which no validation stage detects. Name both directories
whenever the caller knows them.

Exit code 0 with `ok=true` means the run succeeded; any validation failure exits 1 and lists
one entry per failed check. The validator prints a normalised receipt; the caller passes
**only** the `.receipt` sub-object to `--check-result-json`.

**The publish is two steps, and every report node with a completion check follows it.** The
runtime resolves a node's declared completion facts before it applies the blackboard writes
carried by the same mutation, so a node that publishes its facts and completes in one call fails
its own check with a set of `check_fact_mismatch` violations. Publish the facts first, in a
mutation that carries no terminal check, and pass only the receipt on the completing mutation.
C25a states the sequence normatively.

Every value inside `receipt.facts` is a **string** (`"7"`, `"true"`), because the runtime
compares a declared completion-check fact against the blackboard as exact text. Emitting a
number or a boolean there makes node completion fail with `check_fact_mismatch` even though
the recomputation proved the coverage. The blackboard keys bound to those facts carry the
same string values.

## Contract

The four reference documents are normative:
- `references/change-report-contract.md` - H1-H50 (page structure, anchors, class names,
  offline self-containment, language) and A1-A30 (per-unit analysis content: A1-A15 fields,
  A17 related-code refs, the A22 brief, the A25-A30 architectural-element layer, and the
  A18-A21 analysis-depth layer - change class, design dimensions, structured depth blocks,
  and the prefer-diagrams authoring/review default), plus the A13 threshold constants, the
  V17-V37 element-layer, analysis-depth and diagram-placement validation, the strength
  matrix and the strength constants' calibration record. A16 (the purpose layer) is retired.
- `references/analysis-depth.md` - the change taxonomy (A18) x design-dimension (A19) matrix,
  the three-state answer discipline, the A20 depth blocks, the strength-matrix interaction, and
  the honest capability boundary, distilled from ADR / design-doc / code-review / SemVer / C4 /
  refactoring / concurrency / schema-evolution practice.
- `references/coverage-protocol.md` - C1-C39 (manifest format, the six-step enumeration
  algorithm, baseline recording and the C4b snapshot contract, exclusion rules, staleness and
  refresh, sensitive and non-decodable content, the lifecycle coverage disposition, the
  calibration record of the acceptance-gating constants) plus the O1-O9 orchestration contract,
  the V1-V16 failure table and the normalisation rule.
- `references/diagram-spec.md` - D1-D27 (diagram grammar, the two render modes, six types,
  trigger conditions, geometry constants, the prefer-diagrams mechanisms: D20 non-blocking
  suitability advisory, D21 depth-block diagram derivation, D22 the optional sequence SVG
  carrier, D23 the inline-unit vs macro-region diagram placement and page-wide numbering, and
  D24-D27 the component carrier and the derived element map).

The report is a user-facing artefact, so its prose follows the
public `xc-document` human-readable authoring default and the work order's document
language. This Skill declares
only the HTML-specific increment over that contract: section order, class names, anchor
rules, the glossary-to-prose correspondence, the diagram summaries and the previous/next
navigation. It reuses none of the `xc-document` frontmatter, file-format or managed-document
rules: report metadata lives in the HTML `<meta>` elements and the visible report
information section.

## Blackboard

The report group's blackboard is a **partition**: the caller seeds one half before the group
runs, the nodes publish the other half. The two halves below are disjoint and their union is
exactly the 26 keys `assets/change-report-flow.json` declares.

**The declaration is not a safety net.** Embedding a subtree copies **no** child template
defaults: only node structure is composed, and the parent runtime blackboard stays the shared
control plane. A caller key that is declared but never written is therefore **absent** from the
mounted blackboard - it is not the empty string, it is not the declared value, and no guard, loop
condition or completion-fact selector resolves it. Two measured consequences follow, and both are
silent-where-it-matters:

- **An omitted gate key skips the human gate.** With `report.gate_required` unwritten, the
  `report.gate_required == true` guard resolves false and `report-gate` is skipped, so the report
  is never shown to a human and the subtree still seals complete. `report.gate_required` is the
  key gate-required work orders must publish.
- **Unpublished selectors and paths fail far from the cause.** An unwritten completion-fact source
  makes the node fail `completion_requirements_failed` with `check_subject_source_missing` or
  `check_fact_source_missing` instead of naming the key the caller owed, and an unwritten or empty
  `report.path` reaches the validator as an empty path, so it reports a generic file error rather
  than the unpublished key. `assets/change-report-flow.json` declaring a value means the
  **subtree** declares it, never that the caller may rely on it.

Publish every key below with the value this work order actually uses, before the group's first
node runs.

**Caller half - the thirteen keys the caller publishes before the group runs, with the initial
value each one carries on a tree that declares it:**

```text
report.path=""                 report.manifest_path=""
report.baseline_commit=""      report.baseline_digest=""
report.language="en"           report.strength="standard"
report.gate_required="false"   report.gate_outcome="not-run"
report.gate_rework_required="false"   report.gate_recovery_required="false"
report.round="1"               report.refresh_count="0"    report.refresh_reason="initial"
```

Seven of them are read by the engine itself before any writer inside the subtree runs: the three
guard and loop keys (`report.gate_required`, `report.gate_recovery_required`,
`report.gate_rework_required`) and the four completion-fact sources a selector resolves
(`report.path`, `report.manifest_path`, `report.strength`, `report.round`). The other six are
read by the subtree's own worker instructions and by no guard, loop condition or selector:
`report.baseline_commit`, `report.baseline_digest`, `report.language`, `report.gate_outcome`,
`report.refresh_count`, `report.refresh_reason`. The caller's obligation is the criterion, not
the guard: seed every key the engine or a node inside the subtree reads before a writer
publishes it. `report.round` is one of the thirteen, not a fourteenth key, and its convention is
protocol O4: publish the 1-based index of the pass being entered, before `prepare-manifest`
runs, so nothing pre-increments it.

**Node half - the other thirteen keys, published from inside the group:**

```text
report.baseline_algorithm
report.strength_upgrade_reason
report.accuracy_open_issues
report.run_required
report.units_total / report.units_covered / report.excluded_total / report.pre_existing_total
report.hash_bound / report.token_bound
report.coverage / report.self_contained / report.head_current
```

The caller does not seed these. `report.baseline_algorithm` is declaration-only in the caller's
own output: the capture tool's `--format keys` prints it, and no node reads it. The manifest step
publishes the unit and exclusion counters and derives `report.run_required`; the coverage and
final validations publish the binding counters and the receipt facts; the accuracy review owns
`report.accuracy_open_issues`; the manifest step owns `report.strength_upgrade_reason`.

`report.strength` may only be raised by the manifest step when the measured unit count
exceeds the minimal-level ceiling. It is never lowered.

The orchestration package lives in `assets/change-report-flow.json` (the single source of
truth) and `assets/change-report-template.xml` (built from it by
`xc-orchestration-author`'s `template_builder.py`). **Never hand-write the template XML.**

## Constraint summary

- Standard library only. No third-party highlighting library, no diagram library, no network
  access at generation time or at read time.
- The report is one file with no external resource, no web font, no script runtime and no
  fetch-capable element. Diagram specifications are the only JSON script blocks, and their
  shape is fixed.
- Every analysable change unit has exactly one recomputation code block, one anchor, one
  change-map row and one analysis section carrying the eight required fields.
- Secret-shaped content never reaches the report; a redaction marker keeps the structure
  recomputable.
- Non-UTF-8 content is decoded with replacement characters and the degradation is visible in
  both the manifest and the report; it is never silently turned into mojibake.
- Skills are project-independent: no consumer language, framework, directory layout or
  business rule is baked into the package. Project differences arrive through
  `work_order.document_language` and the project bridge.
- Temporary files, including the baseline snapshots and any intermediate render, live under
  the workbench `tmp/` directory and are never declared as artefacts.

## Honest capability boundary

State these limits wherever the report's guarantees are described; do not soften them.

- The validator proves that the analysis **exists, is complete and is bound to the code it
  cites**. Hash recomputation (V10) and token intersection (V11) check binding, not meaning.
- The element layer (V17/V18, V33-V37) proves that elements exist, that each carries its six
  parts, that every unit is bound, and that the before and after states differ. It cannot prove
  that the element division is the right one: a report that puts every unit in one element and
  writes six plausible paragraphs passes every check. That boundary is deliberate and is tested
  by the reverse case; only the accuracy review (and the human gate, when open) can report a bad
  division.
- "The explanation is correct" is judged by the accuracy review worker, not by a script. The
  worker reads the repository, the diff and the report; it can find an explanation that
  contradicts the code, and it cannot find code that contradicts the requirements.
- A worker can also judge wrongly: it may pass a wrong explanation or flag a correct one.
  Nothing mechanical detects that. The mechanism moves the residual risk from "nobody
  checked" to "somebody checked and may still be wrong"; it does not reach zero.
- The human gate is optional and closed by default. When it is closed, the synchronous
  confirmation is gone; the two on-demand paths (re-run the report group, or raise an
  ordinary change request) remain.
- `sequence`, `class` and `er` diagrams are carried by deterministic tables. They promise
  content completeness and ordering; they promise no layout quality.
- The completion-check receipt is an unsigned caller self-report. Any structurally matching
  receipt is accepted, so the receipt alone proves nothing: the proof is the recomputation a
  third party can repeat against the same worktree, baseline and HTML.
- The proportional baseline snapshot holds only the dirty-at-open tracked paths, so the C4
  digest is **not** recomputable from the snapshot directory alone: a third party also needs the
  baseline commit's objects, which is where a clean path's open bytes live. Those bytes are read
  by the object id the commit's tree resolves and batched through one `git cat-file --batch`,
  never through a `git show <commit>:<path>` worktree spelling, so a checkout whose path length
  crosses the host's path limit captures and verifies like any other. The manifest's own
  baseline-content reads - a candidate path's row, not the digest - are separate and not yet
  converted: they still spell `commit:path`, which C4b records as a pre-existing limit with its
  measured consequence, and converting those readers is deferred work. The commit's
  availability is therefore a real precondition of the proof, and when a history rewrite removes
  it the clean-path side is gone - reported as
  `baseline_worktree_snapshot_commit_unavailable`, never as a complete report. A commit that
  cannot be enumerated at all is the stronger case: the manifest fails closed rather than
  publishing `run_required=false` from an enumeration that never happened, so the zero-unit rule
  cannot turn it into a legal skip. The same precondition bounds the pre-existing/dirty
  boundary: the snapshot shows *which* paths were dirty, and only the commit shows what they were
  dirty from.
- A tracked path with no readable open-state bytes at open - absent from the worktree, or present
  but unopenable - is omitted from the digest on every side and named in the record
  (`deleted_paths`, or `tracked_path_unreadable:<path>`). Its `files[].baseline_sha256` is
  therefore the empty hash and never the baseline commit's blob, and a manifest whose provenance
  alignment needs that path's opening content records the exclusion rather than inventing it.
- One report covers one work order. There is no delivery-level aggregate report; the result
  document carries the pointers to the reports of the sibling work orders.
