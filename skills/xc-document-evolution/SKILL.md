---
name: "xc-document-evolution"
description: "Provides a reusable orchestration subtree for writing, validating, reviewing, revising, and gating managed workflow documents. Invoke when a workflow needs durable document evolution."
---

# XC Document Evolution

`xc-document-evolution` provides the reusable control-flow template for managed document work. Domain workflows embed this subtree rather than duplicating document authoring, validation, review, revision, and user-gate logic.

## Required Blackboard Values

- `document.path`: Target document path inside the context repository.
- `document.kind`: Expected `xc-document` document kind.
- `document.template`: Template path or `none` for an existing document.
- `document.inputs`: Comma-separated source document and artifact paths.
- `document.contract`: Path to the domain authoring contract or reference.
- `document.review_required`: `true` or `false`.
- `document.gate_required`: `true` or `false`.
- `document.review.open_issues`: Set by the review node before loop evaluation.

## Template

The managed template is `assets/document-evolution-template.xml`. It has this control shape:

```text
write document
-> validate draft
-> optional review/revise loop
-> optional user gate
-> validate final document
```

The calling Skill supplies document-specific instructions, inputs, review dimensions, and gate questions through the tree node contract and blackboard. It MAY dynamically add further revise, review, or gate nodes when user feedback requires them.

## Node Contracts

- The write or revise worker uses `xc-document` templates and writes the target document immediately.
- Every validator node invokes `xc-document` with `document.path` and `document.kind`.
- Review workers write node artifacts under the active run's `artifacts/<node-id>/` directory and set `document.review.open_issues`.
- A revision worker changes only the target document and records its artifact path when completing.
- User gates are executed by the main session and record short decisions in the blackboard. Long feedback becomes a node artifact.

## Constraints

- Document writes MUST complete before their node is marked successful.
- Nodes that declare the document as an artifact use terminal runtime checkpoint commits when `auto_commit=true`.
- The template never stores document body content, review reports, or dynamic workflow state in the tree.
- The document's frontmatter is validated through `xc-document`; no worker directly edits runtime XML.
