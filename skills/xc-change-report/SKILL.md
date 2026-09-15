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

## Position in the lifecycle

- In the full lifecycle the report group sits between the verification group and the result
  document: only after the code is implemented and verified does the report describe a state
  that still exists.
- Where an independent review or a bridge-declared review step exists, the report is produced
  before that review, because the report is the reviewer's input.
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
    workbench `tmp/` directory. They are what makes pre-existing edits separable and what
    keeps a deletion of a never-tracked file recomputable.
- `language` - `string`; required
  - Scope: `work_order.document_language`. It is the language of the report body; code,
    paths, identifiers, commands and machine output stay verbatim.
- `strength` - `enum`; required
  - Allowed values: `minimal`, `standard`, `full`.
  - Scope: content thickness only. All three levels run every mechanical check and the
    accuracy review.
- `gate_required` - `boolean`; default `false`
  - Scope: opens the optional human gate. It is not a property of the strength level.
- `stage` - `enum`; required for validation
  - Allowed values: `coverage`, `final`.
  - Scope: `coverage` runs V1-V13; `final` additionally recomputes V14.

## Commands

Run each script from the Skill package; scripts resolve their own package location and never
take a script path from the caller.

```text
python scripts/build_manifest.py --repo R --work-order-id W --baseline-commit C
       [--baseline-digest D] [--baseline-worktree-dir T] [--baseline-untracked-dir U]
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

`--tmp-dir` is the workbench `tmp/` directory and H4/C37 require it: the baseline snapshots,
the C37 `O`/`B`/`H` no-index scratch files and the skeleton's intermediate diff inputs must all
land there, never in the OS temp directory. Both scripts accept it and both fall back to the OS
temp directory only when the caller omits it; a caller that omits it violates H4/C37.

Exit code 0 with `ok=true` means the run succeeded; any validation failure exits 1 and lists
one entry per failed check. The validator prints a normalised receipt; the caller passes
**only** the `.receipt` sub-object to `--check-result-json`.

Every value inside `receipt.facts` is a **string** (`"7"`, `"true"`), because the runtime
compares a declared completion-check fact against the blackboard as exact text. Emitting a
number or a boolean there makes node completion fail with `check_fact_mismatch` even though
the recomputation proved the coverage. The blackboard keys bound to those facts carry the
same string values.

## Contract

The three reference documents are normative:
- `references/change-report-contract.md` - H1-H41 (page structure, anchors, class names,
  offline self-containment, language) and A1-A15 (per-unit analysis content), plus the
  A13 threshold constants and the strength matrix.
- `references/coverage-protocol.md` - C1-C38 (manifest format, the six-step enumeration
  algorithm, baseline recording, exclusion rules, staleness and refresh, sensitive and
  non-decodable content) plus the V1-V14 failure table and the normalisation rule.
- `references/diagram-spec.md` - D1-D18 (diagram grammar, the two render modes, trigger
  conditions, geometry constants).

The report is a user-facing artefact, so its prose follows the
public `xc-document` human-readable authoring default and the work order's document
language. This Skill declares
only the HTML-specific increment over that contract: section order, class names, anchor
rules, the glossary-to-prose correspondence, the diagram summaries and the previous/next
navigation. It reuses none of the `xc-document` frontmatter, file-format or managed-document
rules: report metadata lives in the HTML `<meta>` elements and the visible report
information section.

## Blackboard

The caller publishes these keys before the group runs; the nodes publish the rest.

```text
report.path / report.manifest_path
report.baseline_commit / report.baseline_digest
report.language / report.strength
report.gate_required / report.gate_outcome
report.accuracy_open_issues
report.gate_rework_required / report.gate_recovery_required
report.round / report.refresh_count / report.refresh_reason
report.units_total / report.units_covered / report.excluded_total / report.pre_existing_total
report.run_required / report.hash_bound / report.token_bound
report.coverage / report.self_contained / report.head_current
```

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
- One report covers one work order. There is no delivery-level aggregate report; the result
  document carries the pointers to the reports of the sibling work orders.
