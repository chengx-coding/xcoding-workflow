---
name: "xc-feature-reconciliation"
description: "Reconciles an existing feature's approved baselines with current code and test evidence before an ordinary work order selects a change solution. Invoke once per related feature in an ordinary work order."
---

# XC Feature Reconciliation

`xc-feature-reconciliation` supplies the reusable subtree required by an ordinary work order that references existing features. It applies the two-layer fact rule: code and executable tests describe current implementation evidence; feature baselines describe approved target intent.

## Parameters

- `workbench_path` - `path`; required
  - Scope: Existing ordinary workbench that owns `analysis.md` and reconciliation artifacts.

- `feature_id` - `string`; required
  - Scope: Existing `.xcoding/features/<feature-id>/` directory. The Skill never creates it.

- `feature_dir` - `path`; required
  - Scope: Existing feature baseline directory.

## Template

Embed `assets/feature-reconciliation-template.xml` beneath the ordinary work order's `reconciliation-group` with a unique instance ID. Reconciliation instances are serialized for baseline changes. Independent read-only investigation may occur before or alongside the subtree when its artifacts and synthesis boundaries are explicit.

Set the shared blackboard values for the current instance:

- `reconciliation.feature_id`
- `reconciliation.needs_baseline_sync`
- `reconciliation.has_ambiguous_conflict`
- `reconciliation.provenance_source_ids`
- `reconciliation.conflict_source_ids`
- `reconciliation.conflict_outcome` (`not-required` when no conflict gate is needed)

The caller embeds document-evolution subtrees under `analysis-document` and, when needed, `baseline-sync`. It records decisions through the runtime; it never directly edits the managed tree.

## Reconciliation Rules

- Query feature-document provenance through `xc-orchestration-runtime`, not through direct runtime-tree access.
- Complete `load-feature-provenance` with summary, validation, and exactly one provenance artifact, then publish its terminal ID as the compact JSON array in `reconciliation.provenance_source_ids`.
- Read the `inspect-current-state` control packet before inspection. Complete the node with summary, validation, and exactly one current-state artifact.
- Record all evidence and differences in work order `analysis.md`.
- Evidence-backed differences that preserve product intent may update a feature baseline through document evolution.
- Differences that conflict with requested behavior, approved feature intent, or another work order's newer baseline require `conflict-gate`. Publish the terminal provenance, inspection, and reconciliation-analysis writer IDs in `reconciliation.conflict_source_ids`, read the gate packet, and complete it with `--gate-outcome code-authoritative|baseline-authoritative|revise-goal` plus a non-empty decision. `conflict-continuation` routes only `not-required`, `code-authoritative`, and `baseline-authoritative` to finalization. `revise-goal` opens `conflict-recovery-group`; add the goal revision and successor conflict gate there so an accepting outcome is published before finalization.
- If no decision is available, block `conflict-gate`; blocked is not a successful gate outcome.
- Before baseline modification, re-check provenance and warn the user when another work order has changed the baseline. The workflow does not implement locks or leases.

## Constraints

- Do not treat either code or documents as universally authoritative.
- Do not create a feature directory, overwrite a concurrent change, or silently resolve product ambiguity.
- Store long comparisons in artifacts or `analysis.md`; the blackboard holds only control values.
