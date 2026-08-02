---
name: "xc-new-feature"
description: "Starts and governs a complete managed workflow for developing a new feature, including feature-baseline creation, implementation, verification, and result closure. Invoke when requested behavior requires a new explicitly managed feature."
---

# XC New Feature

`xc-new-feature` is the only normal entry point that creates a new feature directory. It opens one persistent work order, establishes approved feature baselines through document evolution, and schedules implementation and verification through a runtime-managed main tree.

## Parameters

- `workshop_path` - `path`; required
  - Scope: The fixed project `.xcoding` workshop in an independent workshop Git worktree.

- `project_root` - `path`; required
  - Scope: Business repository root supplied to `xc-open-work-order` for workshop-separation validation.

- `feature_id` - `string`; required
  - Scope: Explicit stable ID. Default projects use a lowercase slug; validate any project-specific override through `WORKFLOW.md`.

- `request` - `string`; required
  - Scope: Requested feature outcome, boundaries, and known constraints.

- `auto_commit` - `boolean`; optional
  - Scope: Uses the runtime configuration unless explicitly set by the caller.

- `document_language` - `string`; optional
  - Scope: Explicit simplified BCP 47 language tag for top-level work order documents. When omitted, use the initiating user request's clearly dominant language; if that cannot be decided quickly, use `en`.

## Main Work Order

1. Read `AGENTS.md`, `.xcoding/WORKFLOW.md`, and `.xcoding/KNOWLEDGE.md`.
2. Call `xc-open-work-order` with the feature request topic and the selected `feature_id`.
3. Call `xc-feature init`, then initialize `assets/new-feature-template.xml` in the returned runtime path. Determine, validate through `xc-document`, and set `work_order.document_language` before any document write.
4. Complete `prepare-feature` with the feature directory as a declared artifact.
5. Use `find` to locate each dynamic group and embed `xc-document-evolution` for `goal.md`, work order `solution.md`, and each feature baseline document. Set `document.content_language` from `work_order.document_language` only for top-level work order documents; use the project bridge for feature-baseline language.
6. Schedule evidence and synthesis nodes using `xc-analysis`; write the accepted work order analysis when needed.
7. When evidence leaves a material human-owned decision unresolved, or the user explicitly asks to clarify or stress-test the feature, set `work_order.requires_clarification=true` and embed `xc-clarify` under `clarification-group` before selecting the work order solution.
8. Review the work order solution and feature `contract.md`, `solution.md`, and `verification.md` through document-evolution loops. Publish their four terminal writer IDs as a compact JSON array in `feature.baseline_source_ids`, read the `approve-feature-baseline` control packet, and complete the gate with `--gate-outcome approved|rejected|revision-required` plus a non-empty decision. The default `feature.baseline_gate_outcome=approved` applies only when the optional gate is skipped. Every non-approved value opens `baseline-recovery-group`; add revision and a successor approval gate there, and publish `approved` through that gate before continuing.
9. Add bounded implementation nodes under `implementation-group` only after `approved-baseline-continuation` is selected, using the complete `xc-implementation` dynamic metadata contract, then add verification nodes under `verification-group` using `xc-verification`. Publish each leaf's actual terminal source IDs through its node-specific blackboard key before reading its packet.
10. Create `result.md` through document evolution and complete `finalize-feature`.

Use runtime-returned paths and node IDs only. Dynamic document, analysis, implementation, review, and verification nodes must declare their artifacts and complete through the runtime public interface.
Control-packet source arrays contain only terminal leaf IDs and are written through the runtime; group IDs and guessed references are invalid. If one of the four baseline documents is not yet represented by a terminal writer artifact, keep the approval gate waiting rather than lowering its source or artifact threshold.

When a reachable dynamic group is empty, `next` reports it in
`awaiting_dynamic_groups`. The main session appends the planned work or closes
the group explicitly; it must not classify that control state as an unexplained
deadlock.

## Baseline Requirements

The feature baselines are approved target documents, not dynamic status ledgers:

- `contract.md` contains observable requirements, boundaries, compatibility, and failure semantics.
- `solution.md` contains the approved technical design and implementation invariants.
- `verification.md` contains requirement mapping and verification design.

The implementation may begin only after required approval gates have published `approved`. If approval feedback changes a baseline, add document revision, review, and successor approval nodes in the open recovery group rather than overwriting a completed node or modifying the runtime tree directly.

## Constraints

- Do not create feature documents outside document-evolution nodes.
- Do not collapse task progress into `tasks.md` or `status.md`; the runtime tree owns dynamic state.
- A later explicit language correction updates `work_order.document_language` and revises only declared top-level work order documents and user-facing artifacts; it does not change feature-baseline language.
- Do not create a project Git commit unless the user or project bridge requires it. Workshop terminal checkpoints follow runtime configuration.
