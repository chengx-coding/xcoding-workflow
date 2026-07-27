---
name: "xc-new-feature"
description: "Starts and governs a complete managed workflow for developing a new feature, including feature-baseline creation, implementation, verification, and result closure. Invoke when requested behavior requires a new explicitly managed feature."
---

# XC New Feature

`xc-new-feature` is the only normal entry point that creates a new feature directory. It creates one persistent run, establishes approved feature baselines through document evolution, and schedules implementation and verification through a runtime-managed main tree.

## Parameters

- `context_dir` - `path`; required
  - Scope: The fixed project `.xcoding` directory in an independent context Git worktree.

- `project_root` - `path`; required
  - Scope: Business repository root supplied to `xc-create-run` for context-separation validation.

- `feature_id` - `string`; required
  - Scope: Explicit stable ID. Default projects use a lowercase slug; validate any project-specific override through `WORKFLOW.md`.

- `request` - `string`; required
  - Scope: Requested feature outcome, boundaries, and known constraints.

- `auto_commit` - `boolean`; optional
  - Scope: Uses the runtime configuration unless explicitly set by the caller.

- `document_language` - `string`; optional
  - Scope: Explicit simplified BCP 47 language tag for top-level run documents. When omitted, use the initiating user request's clearly dominant language; if that cannot be decided quickly, use `en`.

## Main Run

1. Read `AGENTS.md`, `.xcoding/WORKFLOW.md`, and `.xcoding/KNOWLEDGE.md`.
2. Call `xc-create-run` with the feature request topic and the selected `feature_id`.
3. Call `xc-feature init`, then initialize `assets/new-feature-template.xml` in the returned runtime directory. Determine, validate through `xc-document`, and set `run.document_language` before any document write.
4. Complete `prepare-feature` with the feature directory as a declared artifact.
5. Use `find` to locate each dynamic group and embed `xc-document-evolution` for `goal.md`, run `solution.md`, and each feature baseline document. Set `document.content_language` from `run.document_language` only for top-level run documents; use the project bridge for feature-baseline language.
6. Schedule evidence and synthesis nodes using `xc-analysis`; write the accepted run analysis when needed.
7. Review and approve the feature `contract.md`, `solution.md`, and `verification.md` through document-evolution loops and `approve-feature-baseline`.
8. Add bounded implementation nodes under `implementation-group`, then verification nodes under `verification-group`.
9. Create `result.md` through document evolution and complete `finalize-feature`.

Use runtime-returned paths and node IDs only. Dynamic document, analysis, implementation, review, and verification nodes must declare their artifacts and complete through the runtime public interface.

## Baseline Requirements

The feature baselines are approved target documents, not dynamic status ledgers:

- `contract.md` contains observable requirements, boundaries, compatibility, and failure semantics.
- `solution.md` contains the approved technical design and implementation invariants.
- `verification.md` contains requirement mapping and verification design.

The implementation may begin only after required approval gates have succeeded. If approval feedback changes a baseline, add document revision and review nodes rather than overwriting a completed node or modifying the runtime tree directly.

## Constraints

- Do not create feature documents outside document-evolution nodes.
- Do not collapse task progress into `tasks.md` or `status.md`; the runtime tree owns dynamic state.
- A later explicit language correction updates `run.document_language` and revises only declared top-level run documents and user-facing artifacts; it does not change feature-baseline language.
- Do not create a project Git commit unless the user or project bridge requires it. Context terminal checkpoints follow runtime configuration.
