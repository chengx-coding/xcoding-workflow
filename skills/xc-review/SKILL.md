---
name: "xc-review"
description: "Reviews managed documents, solutions, code changes, or verification evidence and records traceable findings as a node artifact. Invoke when a workflow requires independent quality assessment before proceeding."
---

# XC Review

`xc-review` supplies the public review method used by document-evolution loops and lifecycle review nodes. It evaluates an immutable review input and produces a node artifact; the caller owns remediation, retries, gates, and state transitions.

## Parameters

- `review_kind` - `enum`; required
  - Allowed values: `contract`, `solution`, `verification`, `work-order-document`, `code`, `diagnosis`, `general`.
  - Scope: Selects the relevant review dimensions.

- `inputs` - `path[]`; required
  - Scope: Documents, source paths, diffs, test outputs, or artifacts to assess.

- `artifact_path` - `path`; required
  - Scope: A node-artifact path under the active workbench's `artifacts/<node-id>/` directory.

- `review_context` - `string`; optional
  - Scope: Acceptance criteria, exclusions, compatibility constraints, or known risks supplied by the caller.

## Method

Review structure, cross-reference consistency, evidence sufficiency, error handling, compatibility, validation coverage, and scope boundaries appropriate to `review_kind`. For human-facing documents, also review the public `xc-document` authoring dimensions: audience fit, purpose or conclusion before detail, progressive disclosure, first-use terminology explanations, concision, and preservation of material facts, constraints, evidence, risks, and open decisions. Apply explicit user authoring requirements when supplied instead of conflicting style defaults. Code review additionally considers correctness, security, concurrency, robustness, performance, portability, and regression risk.

Every required finding includes severity (`critical`, `high`, `medium`, or `low`), confidence, evidence location, impact, and closure condition. Do not emit ungrounded quality judgments. Separate required findings from non-blocking observations.

## Output

Write a validated `node-artifact` document containing the scope, evidence reviewed, findings, coverage limits, and conclusion. The worker sets only the caller-declared short blackboard value, such as `document.review.open_issues`, through the runtime public command. Review artifacts default to internal English; use the supplied `metadata.artifact.*` contract only when the caller explicitly requests a user-facing report. A user-facing report follows the public `xc-document` human-readable authoring default and supplied explicit requirements while preserving exact evidence.

## Constraints

- Review is read-only with respect to the reviewed product and managed document.
- The caller decides whether a finding requires a revision node, user gate, failure, or accepted risk.
- Do not create generic logs or retain raw command transcripts as a default artifact.
