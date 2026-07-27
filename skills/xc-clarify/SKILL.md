---
name: "xc-clarify"
description: "Clarifies material human decisions in an existing managed run before solution selection. Invoke when a request or stated plan remains ambiguous after evidence collection, or when the user explicitly asks to clarify or stress-test it."
---

# XC Clarify

`xc-clarify` turns unresolved, human-owned decisions into a bounded, traceable clarification session. It complements `xc-analysis`: analysis establishes facts and alternatives; clarification asks only for decisions that evidence cannot answer.

It has two modes:

- `discover`: turn a vague request into explicit goals, boundaries, and material decisions.
- `challenge`: pressure-test a stated plan for assumptions, conflicts, and material gaps.

## Parameters

- `run_dir` - `path`; required
  - Scope: Existing managed run that owns the clarification artifacts.

- `mode` - `enum`; required
  - Allowed values: `discover`, `challenge`.
  - Scope: Selects the clarification posture, not the lifecycle or implementation strategy.

- `subject` - `string`; required
  - Scope: The request, plan, or decision area being clarified.

- `inputs` - `path[]`; optional
  - Scope: Request text, analysis artifacts, feature baselines, source paths, test results, and project bridge references.

- `instance_id` - `string`; required
  - Scope: Unique lowercase kebab-case ID used when embedding the template.

- `initial_decision_budget` - `integer`; optional, defaults to `12`
  - Scope: Number of material decision Gates allowed before a user-confirmed budget Gate.

## Caller Contract

`xc-clarify` is an embedded subtree, not a standalone run. The caller must create or resume the run, locate its `clarification-group`, and set these short blackboard values before embedding:

```text
clarification.mode
clarification.subject
clarification.instance_id
clarification.status
clarification.question_count
clarification.limit
clarification.pending_material
clarification.outcome
clarification.session_artifact
```

Embed `assets/clarify-template.xml` through `xc-orchestration-runtime`. Child-template defaults are not copied into the parent blackboard. Only one clarification instance may be active in a caller group because the blackboard is shared; clarify multiple subjects sequentially.

`clarification.session_artifact` must point to one `node-artifact` document beneath the active run's `artifacts/<open-session-node-id>/` directory.

## Runtime Flow

The managed template runs these fixed nodes in order:

```text
open session record
-> gather context
-> map decisions
-> seed questioning
-> dynamic question group
-> synthesize session
-> finalize clarification
```

The opening worker creates the single session artifact. The following fixed workers append evidence and the decision map to it.

`seed-questioning` is a main-executor task. It reads the decision map and, before it completes, adds the first main-executor Gate beneath the empty dynamic `question-group`. When no material decision remains, it adds a closing confirmation Gate instead. This prevents an empty dynamic group from blocking the sequence.

For every decision Gate, the main session:

1. Checks whether source, tests, documents, or accepted artifacts answer the question before asking the user.
2. Asks exactly one material, human-owned decision.
3. States the evidence, recommendation, rationale, cost or risk, and at least one viable alternative.
4. Appends the user's full response to the session artifact and stores only short control values in the blackboard.
5. Adds the successor Gate or closing Gate through the runtime public API before completing the current Gate.

The main session must not batch questions, silently reconcile contradictions, or accept a recommended option by default. A user may choose another option, record accepted risk, or request a bounded experiment with an owner, trigger, and acceptance condition.

Before creating questions `13`, `25`, and each later twelve-question boundary, add a budget Gate. The user decides whether to close the session, defer or reframe work as a bounded experiment, or continue. Continuing increases `clarification.limit` by `12`.

## Completion and Handoff

Clarification is ready only when no material decision remains unresolved and every remaining uncertainty is explicitly accepted, deferred, or represented by a bounded experiment. The final worker appends the decision summary, deferred experiments, residual risks, and recommended handoff to the session artifact.

The caller owns document evolution. It uses the session artifact to update `analysis.md` and then selects `solution.md` through its existing approval gate. `xc-clarify` does not modify product code, feature baselines, run solutions, or runtime XML directly.

## Integration

- `xc-run` embeds this subtree after analysis and any feature reconciliation, before solution selection, when `run.requires_clarification=true`.
- `xc-new-feature` embeds it after analysis and before the run solution when `run.requires_clarification=true`.
- An explicit user request to clarify or stress-test work first enters the appropriate lifecycle, then embeds this subtree.

## Constraints

- Use `xc-orchestration-runtime` for every tree read and write.
- Use `xc-document` for session-artifact structure and validation.
- Keep long evidence, questions, and answers in the session artifact, never in blackboard values.
- Do not use clarification to replace evidence gathering, independent review, user approval of a solution, or implementation verification.
