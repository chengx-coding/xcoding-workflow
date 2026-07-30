---
name: "xc-feature-adoption"
description: "Explicitly adopts an existing unmanaged feature by deriving durable feature baselines from code and test evidence. Invoke when a legacy or manually developed feature needs managed future evolution."
---

# XC Feature Adoption

`xc-feature-adoption` is the only workflow that brings an existing feature under managed baselines without implementing a new product change. It treats code and executable tests as evidence of current behavior, records gaps, and asks the user to approve the resulting baseline or resolve target-intent conflicts.

## Parameters

- `workshop_path` - `path`; required
  - Scope: The fixed project `.xcoding` workshop.

- `project_root` - `path`; required
  - Scope: Business repository root supplied to `xc-open-work-order`.

- `feature_id` - `string`; required
  - Scope: Explicit stable ID for a currently unmanaged feature.

- `code_entry` - `string`; required
  - Scope: Existing code boundary, module, interface, or path set to analyze.

- `request` - `string`; optional
  - Scope: Motivation, known future changes, or adoption constraints.

- `document_language` - `string`; optional
  - Scope: Explicit simplified BCP 47 language tag for top-level work order documents. When omitted, use the initiating user request's clearly dominant language; if that cannot be decided quickly, use `en`.

## Main Work Order

1. Read the project bridge and knowledge guidance, then open an adoption work order through `xc-open-work-order`. Determine, validate through `xc-document`, and set `work_order.document_language` before any document write.
2. Use `xc-feature init` only after confirming that the feature is not already managed.
3. Initialize `assets/feature-adoption-template.xml` in the returned runtime path and complete `prepare-adoption`.
4. Create `goal.md` and evidence-driven `analysis.md` through document-evolution nodes, setting `document.content_language` from `work_order.document_language`. Record code boundaries, tests, behavior, uncertainty, and any product-intent gap.
5. Build feature `contract.md`, `solution.md`, and `verification.md` through separate document-evolution subtrees.
6. Present the resulting baseline through `approve-adopted-baseline`. Add revision, review, or user-gate nodes when evidence is incomplete or intended behavior cannot be derived safely.
7. Create `result.md` and complete `finalize-adoption`.

## Adoption Rules

- Adoption does not silently change product behavior or repair code.
- Baselines should state current evidenced behavior and clearly separate unknowns or target changes.
- If the user wants a product change after adoption, open a separate `xc-work`.
- The feature directory is created before its baseline documents but becomes useful only after the approval gate or an explicit blocked result.

## Constraints

- Do not infer a feature directory from an ordinary work order.
- Do not convert historical code behavior into approved target intent without evidence and confirmation.
- Preserve evidence and unresolved gaps in `analysis.md`, `result.md`, and node artifacts, not in runtime blackboard fields.
- A later explicit language correction revises declared top-level work order documents and user-facing artifacts only; adopted feature baselines remain governed by the project bridge.
