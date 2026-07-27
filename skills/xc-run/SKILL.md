---
name: "xc-run"
description: "Runs managed investigation, iteration, repair, review, maintenance, or cross-feature work without implicitly creating a feature. Invoke for persistent work that may relate to zero, one, or multiple existing features."
---

# XC Run

`xc-run` is the common lifecycle for existing-code work. It always creates a durable run and `goal.md`; `analysis.md` and run `solution.md` are created only when their semantic purpose is needed. A run may reference no feature, a single existing feature, or multiple existing features.

## Parameters

- `context_dir` - `path`; required
  - Scope: The fixed project `.xcoding` context directory.

- `project_root` - `path`; required
  - Scope: Business repository root supplied to `xc-create-run`.

- `request` - `string`; required
  - Scope: Requested investigation, change, repair, review, or maintenance outcome.

- `feature_ids` - `string[]`; optional
  - Scope: Existing related feature identifiers. An empty list is valid.

- `mode` - `enum`; optional, defaults to `change`
  - Allowed values: `investigation`, `change`, `repair`, `review`, `maintenance`.
  - Scope: Controls default analysis, solution, implementation, and verification gates. The runtime blackboard remains authoritative for the selected execution path.

- `document_language` - `string`; optional
  - Scope: Explicit simplified BCP 47 language tag for top-level run documents. When omitted, use the initiating user request's clearly dominant language; if that cannot be decided quickly, use `en`.

## Main Run

1. Read `AGENTS.md`, `.xcoding/WORKFLOW.md`, and `.xcoding/KNOWLEDGE.md`.
2. Verify every supplied `feature_id` already exists. Do not create or adopt a feature.
3. Call `xc-create-run`, initialize `assets/run-template.xml`, determine and validate `run.document_language` through `xc-document`, then complete `prepare-run`. An explicit `document_language` wins; otherwise use only the initiating request's clearly dominant language or `en`.
4. Create `goal.md` through document evolution. Before every top-level run document subtree, set `document.content_language` to `run.document_language`. Set blackboard controls based on the requested mode and required gates.
5. When analysis is needed, schedule `xc-analysis` nodes and synthesize accepted evidence into `analysis.md`.
6. When feature IDs are present, embed `xc-feature-reconciliation` sequentially under `reconciliation-group` before selecting a run solution.
7. When evidence leaves a material human-owned decision unresolved, or the user explicitly asks to clarify or stress-test work, set `run.requires_clarification=true` and embed `xc-clarify` under `clarification-group`. The group must complete before selecting a solution.
8. Create run `solution.md` when a change strategy must be selected. Use `approve-run-solution` for material decisions or unresolved risk.
9. Add approved implementation nodes through `xc-implementation`, then verification nodes through `xc-verification`.
10. Create `result.md` through document evolution and complete `finalize-run`.

When `next` or `summary` reports `awaiting_dynamic_groups`, the main session
must append the planned subtree or explicitly close an intentionally empty
group before treating the run as blocked. An explicit correction to a
successful run first passes through the owning user gate and runtime `reopen`;
ordinary work must not append to a sealed historical tree.

## Mode Rules

- `investigation`: normally requires analysis and result, but may skip solution, implementation, and verification.
- `review`: normally requires analysis and review artifacts, but does not modify reviewed inputs.
- `repair`: uses `xc-diagnosis` when root cause is uncertain, then follows the regular solution, implementation, and verification path.
- `change` and `maintenance`: select only the documents and nodes necessary for the requested outcome.

## Reconciliation and Concurrency

Runs may analyze and design for the same feature concurrently. Before any baseline modification, the active run re-checks feature provenance and warns when another run changed the baseline. The workflow does not use feature locks or leases. Users coordinate the serialized timing of actual feature baseline modifications.

## Constraints

- An ordinary run never implicitly creates `.xcoding/features/<feature-id>/`.
- Code and executable tests are evidence of current behavior; feature baselines are approved target intent. Ambiguous conflict requires a user gate.
- Dynamic state, task ordering, retry state, and blockers remain in the runtime tree, not in documents.
- Do not re-detect language from later user messages. A user may explicitly correct `run.document_language`; revise already declared top-level run documents and `metadata.artifact.audience=user` reports through runtime-managed document-evolution work.
