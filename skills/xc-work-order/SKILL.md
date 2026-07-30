---
name: "xc-work-order"
description: "Runs a managed work order for investigation, iteration, repair, review, maintenance, or cross-feature work without implicitly creating a feature. Invoke for persistent work that may relate to zero, one, or multiple existing features."
---

# XC Work Order

`xc-work-order` is the common lifecycle for existing-code work. It always opens a durable work order and creates `goal.md`; `analysis.md` and `solution.md` are created only when their semantic purpose is needed. A work order may reference no feature, one existing feature, or multiple existing features.

## Parameters

- `workshop_path` - `path`; required
  - Scope: The fixed project `.xcoding` workshop.

- `project_root` - `path`; required
  - Scope: Business repository root supplied to `xc-open-work-order`.

- `request` - `string`; required
  - Scope: Requested investigation, change, repair, review, or maintenance outcome.

- `feature_ids` - `string[]`; optional
  - Scope: Existing related feature identifiers. An empty list is valid.

- `mode` - `enum`; optional, defaults to `change`
  - Allowed values: `investigation`, `change`, `repair`, `review`, `maintenance`.
  - Scope: Controls default analysis, solution, implementation, and verification gates. The runtime blackboard remains authoritative for the selected execution path.

- `document_language` - `string`; optional
  - Scope: Explicit simplified BCP 47 language tag for top-level work order documents. When omitted, use the initiating user request's clearly dominant language; if that cannot be decided quickly, use `en`.

## Main Work Order

1. Read `AGENTS.md`, `.xcoding/WORKFLOW.md`, and `.xcoding/KNOWLEDGE.md`.
2. Verify every supplied `feature_id` already exists. Do not create or adopt a feature.
3. Call `xc-open-work-order`, initialize `assets/work-order-template.xml`, determine and validate `work_order.document_language` through `xc-document`, then complete `prepare-work-order`. An explicit `document_language` wins; otherwise use only the initiating request's clearly dominant language or `en`.
4. Create `goal.md` through document evolution. Before every top-level work order document subtree, set `document.content_language` to `work_order.document_language`. Set blackboard controls based on the requested mode and required gates.
5. When analysis is needed, schedule `xc-analysis` nodes and synthesize accepted evidence into `analysis.md`.
6. When feature IDs are present, embed `xc-feature-reconciliation` sequentially under `reconciliation-group` before selecting a work order solution.
7. When evidence leaves a material human-owned decision unresolved, or the user explicitly asks to clarify or stress-test work, set `work_order.requires_clarification=true` and embed `xc-clarify` under `clarification-group`. The group must complete before selecting a solution.
8. Create `solution.md` when a change strategy must be selected. Use `approve-work-order-solution` for material decisions or unresolved risk.
9. Add approved implementation nodes through `xc-implementation`, then verification nodes through `xc-verification`.
10. Create `result.md` through document evolution and complete `finalize-work-order`.

When `next` or `summary` reports `awaiting_dynamic_groups`, the main session
must append the planned subtree or explicitly close an intentionally empty
group before treating the work order as blocked. An explicit correction to a
successful work order first passes through the owning user gate and runtime `reopen`;
ordinary work must not append to a sealed historical tree.

## Mode Rules

- `investigation`: normally requires analysis and result, but may skip solution, implementation, and verification.
- `review`: normally requires analysis and review artifacts, but does not modify reviewed inputs.
- `repair`: uses `xc-diagnosis` when root cause is uncertain, then follows the regular solution, implementation, and verification path.
- `change` and `maintenance`: select only the documents and nodes necessary for the requested outcome.

## Reconciliation and Concurrency

Work orders may analyze and design for the same feature concurrently. Before any baseline modification, the active work order re-checks feature provenance and warns when another work order changed the baseline. The workflow does not use feature locks or leases. Users coordinate the serialized timing of actual feature baseline modifications.

## Constraints

- An ordinary work order never implicitly creates `.xcoding/features/<feature-id>/`.
- Code and executable tests are evidence of current behavior; feature baselines are approved target intent. Ambiguous conflict requires a user gate.
- Dynamic state, task ordering, retry state, and blockers remain in the runtime tree, not in documents.
- Do not re-detect language from later user messages. A user may explicitly correct `work_order.document_language`; revise already declared top-level work order documents and `metadata.artifact.audience=user` reports through runtime-managed document-evolution work.
