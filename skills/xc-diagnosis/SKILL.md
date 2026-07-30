---
name: "xc-diagnosis"
description: "Investigates a reported problem through reproduction and evidence collection without applying product repairs. Invoke when root cause, failure mode, or repair direction is uncertain."
---

# XC Diagnosis

`xc-diagnosis` is the diagnosis contract for an existing managed work order. The caller's runtime tree schedules clarification, reproduction, evidence collection, root-cause analysis, and optional verification as separate nodes. Diagnosis writes work order `analysis.md` and node artifacts; it does not apply the product repair.

## Parameters

- `workbench_path` - `path`; required
  - Scope: Existing workbench that owns `goal.md`, optional `analysis.md`, and diagnosis artifacts.

- `problem_statement` - `string`; required
  - Scope: Observed behavior, expected behavior, known reproduction information, and affected scope.

- `mode` - `enum`; optional, defaults to `diagnose`
  - Allowed values: `diagnose`, `verify`.
  - Scope: `verify` reuses an existing diagnosis artifact after a separate repair work order.

- `inputs` - `path[]`; optional
  - Scope: Reports, prior artifacts, code entry points, tests, and project bridge references.

## Required Evidence Flow

1. Clarify observable failure, expected behavior, scope, and safe reproduction conditions in the work order goal or analysis.
2. Attempt reproduction using project-bridge commands and available tests before introducing instrumentation.
3. Collect bounded evidence from code, configuration, tests, runtime output, or approved project tools.
4. Record confirmed cause, suspected causes with confidence, non-reproduced conditions, affected boundaries, and a repair direction in `analysis.md`.
5. If a repair is requested and evidence is sufficient, return control to `xc-work`; do not repair inside the diagnosis node.

Diagnosis node artifacts default to internal English. A caller may explicitly request a user-facing diagnosis report through `metadata.artifact.audience=user` and `metadata.artifact.content_language=work_order.document_language`.

## Instrumentation

Temporary diagnostic source changes require explicit caller authorization, a declared artifact describing the exact diff, focused evidence collection, and removal before node completion. If safe removal cannot be established because concurrent changes occurred, block the node and escalate to the main-session user gate.

## Constraints

- Do not represent a suspected cause as confirmed.
- Do not hard-code project logs, test frameworks, environments, or access methods.
- External access, production data, or destructive reproduction prerequisites are blockers, not reasons to fabricate evidence.
