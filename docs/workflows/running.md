**Language:** **English** | [Simplified Chinese (简体中文)](../zh-CN/workflows/running.md)

# Running Managed Work

A managed lifecycle preserves decisions and evidence in documents and artifacts while the orchestration runtime owns execution state. The exact path is selected by the entry workflow and the accepted solution; optional stages are not added merely to fill a template.

## Lifecycle

1. **Load project policy.** Read the project instructions, workshop bridge, and declared knowledge guidance before choosing commands or making project-specific assumptions.
2. **Open and initialize the work order.** Create the durable workbench, initialize its managed tree, and fix the work order document language before writing the first top-level document.
3. **Record the goal.** `goal.md` defines the requested outcome, boundaries, constraints, and acceptance direction.
4. **Establish evidence.** When facts, impact, alternatives, diagnosis, or feature reconciliation are needed, [`xc-analysis`](../../skills/xc-analysis/SKILL.md) records perspective evidence in node artifacts and synthesizes accepted facts into `analysis.md`.
5. **Clarify human decisions.** When evidence cannot answer a material decision, [`xc-clarify`](../../skills/xc-clarify/SKILL.md) asks bounded questions through main-session gates before solution selection. It does not replace investigation.
6. **Select and approve a solution.** `solution.md` records the chosen change, boundaries, risks, compatibility impact, and verification strategy. Material decisions and unresolved risks pass through an explicit user gate.
7. **Implement bounded nodes.** Each [`xc-implementation`](../../skills/xc-implementation/SKILL.md) worker receives one approved scope, changes only owned files, records evidence, and reports through the runtime.
8. **Verify and review.** [`xc-verification`](../../skills/xc-verification/SKILL.md) runs project-defined checks and records coverage gaps. Where independent quality assessment is required, [`xc-review`](../../skills/xc-review/SKILL.md) evaluates immutable inputs and produces traceable findings. Failed evidence returns to the owning lifecycle rather than silently weakening acceptance criteria.
9. **Close the result.** `result.md` summarizes delivered behavior, verification, unresolved risks, and relevant artifacts before the work order is finalized.

Top-level work-order documents are durable records, not a program counter. Dynamic ordering, readiness, loops, retries, blockers, and progress remain in the runtime tree.

## Execution Boundaries

The main session asks the [orchestration runtime](../../skills/xc-orchestration-runtime/SKILL.md) for the next ready node or batch, starts work before delegation, handles user gates, and verifies state after workers return.

Each worker executes exactly one running node. It reads only supplied inputs and references, writes the declared artifact, then calls `complete`, `fail`, or `block`. A worker does not inspect the complete tree, execute sibling work, or decide the next global transition.

Long reports, diffs, and logs belong in artifacts. The blackboard contains short structured values that influence later scheduling or decisions.

## Resuming Work

Resume through the runtime's public commands using the existing tree reference. `next`, `summary`, `show`, and `find` expose the state needed by the main session without direct access to managed storage. Callers use paths and node IDs returned by the runtime rather than reconstructing them.

An open, reachable dynamic group with no children is reported as awaiting work. The main session must add the approved nodes or explicitly close the group; an empty ready list is not automatically a deadlock.

A successfully completed tree is sealed. Additional work requires an explicit user-approved reason and the runtime's reopen operation; ordinary execution does not append to a sealed historical tree.

## Failures And Recovery

- Use `fail` when a node attempted its work and could not satisfy its contract. Preserve the evidence and let the owning lifecycle decide whether to retry, revise, or choose another path.
- Use `block` when progress depends on user input, external access, a safe reproduction prerequisite, or another recoverable condition.
- Treat verification failures as results. Do not alter behavior or acceptance criteria inside a verification node merely to obtain a pass.
- Report state conflicts, sealed-tree responses, and integrity failures to the main session instead of retrying an ambiguous mutation.
- Use runtime diagnostics and explicit integrity repair operations. Never repair checksums or status fields directly.

When runtime checkpoint commits are enabled, terminal transitions and declared workshop artifacts are path-scoped. A failed checkpoint restores the tree transition, so an uncommitted persistence error is not reported as successful completion.
