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

Diagnosis node artifacts default to internal English. A caller may explicitly request a user-facing diagnosis report through `metadata.artifact.audience=user` and `metadata.artifact.content_language=work_order.document_language`. User-facing reports follow the public `xc-document` human-readable authoring default and supplied explicit authoring requirements while preserving exact reproduction and evidence details.

## Instrumentation

Temporary diagnostic source changes require explicit caller authorization, a declared artifact describing the exact diff, focused evidence collection, and removal before node completion. If safe removal cannot be established because concurrent changes occurred, block the node and escalate to the main-session user gate.

### Report exemption for the transient mutation

That temporary mutation is **recorded as an exemption from the work order's change report**; the removal obligation is what replaces the report obligation.

- **Reason.** The mutation is evidence gathering, not a deliverable. The node must remove it before it completes, so by the time a report could be produced the change no longer exists and there is nothing left to report; a report of a change the same lifecycle requires to be gone would describe a state this contract forbids.
- **Criterion.** The exemption holds only while every one of these holds: the caller authorized the mutation explicitly; a declared artifact describes the exact diff; the mutation stays confined to the diagnosis node; and the node verifies removal before it completes. An unremoved or unverifiable mutation is never exempt - it blocks the node instead, so "the mutation could not be removed" is not a state in which this exemption can be claimed.
- **Residual risk.** A mutation that survives unverified removal: if the removal check itself is wrong, or a concurrent writer reintroduces the bytes, the surviving change reaches the enclosing work order's change set explained by nothing. The controlling check already exists outside this Skill - `xc-review` reports a workspace change the reviewed scope created outside the workbench as a required finding, and treats the recorded exception as non-blocking only when removal is verified - and whether a review node runs after this one is the caller's decision, not something this Skill can enforce.

## Constraints

- Do not represent a suspected cause as confirmed.
- Do not hard-code project logs, test frameworks, environments, or access methods.
- External access, production data, or destructive reproduction prerequisites are blockers, not reasons to fabricate evidence.
- Temporary scripts, intermediate outputs, and process files belong under the workbench `tmp/` directory; keep them out of the user home directory, operating-system temporary locations, and any project-repository content outside the workbench, and never declare them as artifacts.
- When the task itself requires a location outside the workbench, record the location, the reason, and the verified removal in the node artifact.
