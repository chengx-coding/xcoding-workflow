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

Workbench-layout review checks the reviewed scope's own file placement: temporary scripts, intermediate outputs, and process files belong under the workbench `tmp/` directory. Report a file that the reviewed node or work order created outside the workbench as a required finding - `high` severity when no exception is recorded, and `medium` severity when the location and the reason are recorded but the verified removal is missing or the file is still present - with its evidence location, its impact, and a closure condition that the file is moved under the workbench `tmp/` directory, removed, or covered by a recorded exception with verified removal. A recorded exception with verified removal is a non-blocking observation rather than a required finding, and a reviewed scope whose files are all inside the workbench `tmp/` directory or at their declared artifact paths yields no finding.

Every required finding includes severity (`critical`, `high`, `medium`, or `low`), confidence, evidence location, impact, and closure condition. Do not emit ungrounded quality judgments. Separate required findings from non-blocking observations.

## Output

Write a validated `node-artifact` document containing the scope, evidence reviewed, findings, coverage limits, and conclusion. The worker sets only the caller-declared short blackboard value, such as `document.review.open_issues`, through the runtime public command. Review artifacts default to internal English; use the supplied `metadata.artifact.*` contract only when the caller explicitly requests a user-facing report. A user-facing report follows the public `xc-document` human-readable authoring default and supplied explicit requirements while preserving exact evidence.

## Constraints

- Review is read-only with respect to the reviewed product and managed document.
- The caller decides whether a finding requires a revision node, user gate, failure, or accepted risk.
- Do not create generic logs or retain raw command transcripts as a default artifact.
- Temporary scripts, intermediate outputs, and process files belong under the workbench `tmp/` directory; keep them out of the user home directory, operating-system temporary locations, and any project-repository content outside the workbench, and never declare them as artifacts.
- When the task itself requires a location outside the workbench, record the location, the reason, and the verified removal in the node artifact.
- Workbench-layout detection stays read-only: report placement findings, and never move or delete the reviewed files.
