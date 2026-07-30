**Language:** **English** | [Simplified Chinese (简体中文)](../zh-CN/concepts/workshops-features.md)

# Workshops, Work Orders, And Features

## The Workshop

Every consumer project uses the fixed conceptual path `.xcoding/` for its managed workshop. The workshop belongs to a Git worktree independent from the project code repository. This keeps workflow documents, runtime checkpoints, and node artifacts out of product commits while preserving their own durable history.

The workshop bridge documents project policy. `WORKFLOW.md` describes project identity, commands, conventions, and constraints. `KNOWLEDGE.md` says whether a project knowledge source exists and how to use it. Neither document is a generic replacement for the canonical `xc-*` Skills.

## Work Orders And Workbenches

A work order is one durable unit of investigation, change, repair, review, or maintenance. The [work-order opener](../../skills/xc-open-work-order/SKILL.md) creates a collision-safe ID and returns authoritative workbench paths without creating documents, runtime trees, feature directories, or commits.

A standard workbench has this conceptual shape:

```text
.xcoding/work-orders/<work-order-id>/
  goal.md
  analysis.md       # when evidence or alternatives are needed
  solution.md       # when a change strategy must be selected
  result.md
  runtime/
  artifacts/
```

`goal.md`, `analysis.md`, `solution.md`, and `result.md` preserve durable intent, evidence, decisions, and outcomes. Dynamic status, ordering, retry state, loop state, and blockers belong to the managed runtime tree. Detailed worker evidence belongs under `artifacts/`, not in the runtime blackboard.

A work order may relate to zero, one, or multiple existing features. The common [work lifecycle](../../skills/xc-work/SKILL.md) does not manufacture a feature merely because a change is persistent.

## Feature Baselines

A managed feature has a stable identifier and three approved baseline documents:

```text
.xcoding/features/<feature-id>/
  contract.md
  solution.md
  verification.md
```

- `contract.md` defines observable requirements, boundaries, compatibility, and failure semantics.
- `solution.md` records the approved technical design and implementation invariants.
- `verification.md` maps requirements to the evidence needed to establish them.

Feature baselines are not task lists or status ledgers. Revisions go through managed document evolution, review, and gates as required.

## Current Evidence And Approved Intent

XC keeps two kinds of truth distinct:

| Source | What it establishes |
| --- | --- |
| Project code and executable tests | Evidence of current implementation behavior |
| Approved feature baselines | Target product intent |

Neither side is universally authoritative. The [feature-reconciliation contract](../../skills/xc-feature-reconciliation/SKILL.md) compares them before an ordinary feature-related work order selects a solution. Evidence-backed drift that preserves intent may update a baseline through a separate document-evolution path. Ambiguous conflict, changed product intent, or concurrent baseline modification requires a user gate.

## When A Feature May Be Created

Feature creation is always explicit:

- [New feature](../../skills/xc-new-feature/SKILL.md) creates a feature for behavior that does not yet have a managed identity, then approves its baselines before implementation.
- [Feature adoption](../../skills/xc-feature-adoption/SKILL.md) creates baselines for existing unmanaged behavior from code and test evidence. Adoption does not silently change or repair the product.
- The [feature directory service](../../skills/xc-feature/SKILL.md) may initialize a directory only for those two workflows.
- Ordinary work orders can reference existing feature IDs but cannot create or adopt one.

This rule prevents an implementation detail or incidental maintenance request from becoming a durable product contract without an explicit lifecycle and approval decision.
