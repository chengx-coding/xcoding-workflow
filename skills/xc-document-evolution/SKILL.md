---
name: "xc-document-evolution"
description: "Provides a reusable orchestration subtree for writing, validating, reviewing, revising, and gating managed workflow documents. Invoke when a workflow needs durable document evolution."
---

# XC Document Evolution

`xc-document-evolution` provides the reusable control-flow template for managed document work. Domain workflows embed this subtree rather than duplicating document authoring, validation, review, revision, and user-gate logic.

## Required Blackboard Values

- `document.path`: Target document path inside the workshop repository.
- `document.kind`: Expected `xc-document` document kind.
- `document.template`: Template path or `none` for an existing document.
- `document.inputs`: Comma-separated source document and artifact paths.
- `document.contract`: Path to the domain authoring contract or reference.
- `document.content_language`: Resolved language tag for the target content. Required for top-level work order documents; project and feature document callers may omit it.
- `document.authoring_requirements`: Optional concise explicit user requirements for format, tone, length, terminology density, or audience. Use an empty string for the `xc-document` human-readable default. Put long requirements in a document or artifact referenced by `document.inputs`.
- `document.receipt.content_language`: Effective language expected from `xc-document`; use `document.content_language` when set, otherwise `en`.
- `document.receipt.audience`: Expected `xc-document` audience; use an empty string for non-node-artifact documents and the resolved audience for node artifacts.
- `document.review_required`: `true` or `false`.
- `document.gate_required`: `true` or `false`.
- `document.gate_outcome`: Initialize to `accepted` when the optional gate is skipped; otherwise it is written atomically by the structured document gate.
- `document.review.open_issues`: Set by the review node before loop evaluation.

## Template

The managed template is `assets/document-evolution-template.xml`. It has this control shape:

```text
write document
-> validate draft
-> optional review/revise loop
-> optional user gate
-> non-accepting recovery group
-> validate final document
```

The calling Skill supplies document-specific instructions, inputs, review dimensions, gate questions, and any explicit `document.authoring_requirements` through the tree node contract and blackboard. The caller sets the requirements value before embedding each document instance and preserves it for revisions unless the user explicitly changes it. It MAY dynamically add further revise, review, or gate nodes when user feedback requires them.

The optional review loop and document gate use `when.policy=latched`. If an
instance skips either branch, later changes to the shared `document.*` keys
must not reactivate that completed instance. Callers still serialize instances
that reuse those shared keys; this template does not provide local blackboard
scope.

## Node Contracts

- The write or revise worker uses `xc-document` templates, applies `document.content_language` when present, and follows the public `xc-document` human-readable authoring default plus any explicit `document.authoring_requirements`. It writes the target document immediately and completes with a summary and exactly one `document.path` artifact.
- Every validator node invokes `xc-document` with `document.path` and `document.kind`, requires exit code zero and top-level `ok=true`, extracts only `.receipt`, and completes with summary, validation, and one `--check-result-json` value. The receipt is an untrusted caller self-report; runtime acceptance does not prove that the validator ran.
- Review workers evaluate domain correctness and the `xc-document` human-readable dimensions: audience fit, progressive disclosure, first-use explanations, concision, and preservation of key information. They write exactly one node artifact under the active workbench's `artifacts/<node-id>/` directory, complete with a summary, and set `document.review.open_issues`.
- A revision worker changes only the target document, preserves explicit `document.authoring_requirements`, applies the central human-readable default, and records exactly that artifact path when completing.
- User gates are executed by the main session with `--gate-outcome accepted|rejected|revision-required` and a non-empty `--decision`; the runtime atomically writes `document.gate_outcome`. `rejected`, `revision-required`, and any other non-accepted value open `document-gate-recovery-group` and keep final validation closed. Add revision and a successor gate inside that group; the successor must publish `accepted` before `validate-final` can run. Long feedback becomes a node artifact.

## Language Corrections

When a user explicitly corrects `work_order.document_language`, the owning lifecycle uses the runtime `artifacts` command to select only declared top-level work order documents and `metadata.artifact.audience=user` reports. It creates a dynamic correction group and embeds the first revision subtree before requesting the next node. Complete each correction subtree before setting the next `document.*` values and embedding the next subtree; keep review and gate flags false unless the user separately requests review.

If the source runtime already succeeded, the owning main session must first
record the explicit user correction through its gate and call runtime `reopen`
with that reason. The reopened epoch is the only path for adding correction
work to a sealed tree.

## Constraints

- Document writes MUST complete before their node is marked successful.
- Nodes that declare the document as an artifact use terminal runtime checkpoint commits when `auto_commit=true`.
- The template never stores document body content, review reports, or dynamic workflow state in the tree.
- The document's frontmatter is validated through `xc-document`; no worker directly edits runtime XML.
