**Language:** **English** | [简体中文](../zh-CN/workflows/running.md)

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

## Adaptive Managed Work

`xc-work operation=adaptive-run` is explicit; existing `run` behavior remains unchanged. The adaptive template initially contains only a root and an open sequence `work-group`. The caller validates a plan receipt, adds every initial required leaf and a plan-specific finalizer, then closes the group before starting work.

A minimal mutation uses one combined implementation/focused-verification worker and the finalizer, for two executable leaves. Top-level documents are added independently only for durable intent, evidence synthesis, material decisions, retained results, or full audit. More demanding facts add capabilities in stable order: goal, analysis or diagnosis, clarification, solution, approval, implementation units, verification scopes, independent review, result, and finalization.

If a worker discovers wider scope or another prerequisite, it blocks before further mutation. The main session may reopen the group, insert re-planning or recovery before the blocked direct child, publish a new plan, then unblock the original leaf to continue or record no-op/rollback evidence. Large work may add reviewed subtrees without a global node ceiling, while each loop remains explicitly bounded.

## Human-Readable Documents

Unless the user explicitly requests another format or style, top-level work-order documents, managed project and feature documents, user-facing artifacts, and project documentation delivered by an implementation node follow the [`xc-document`](../../skills/xc-document/SKILL.md) human-readable default.

Writers lead with purpose, conclusion, or required reader action, then add technical depth after the reader has context. Necessary terms are explained briefly at first use. Repetition and process narration are removed without dropping material facts, constraints, evidence, risks, compatibility impact, or unresolved decisions.

Callers pass concise explicit requirements through `document.authoring_requirements` before embedding document evolution. Long requirements remain in an input document or artifact. Explicit user requirements override style defaults, but not truth, safety, managed structure, provenance, or mandatory evidence.

Exact commands, identifiers, paths, logs, and machine output remain literal when accuracy requires it. Their surrounding explanation and summary remain human-readable. Internal technical artifacts may retain specialist depth for their intended audience.

Readability is a semantic review dimension, not a word-count or sentence-length release score. Reviewers check audience fit, progressive disclosure, first-use explanations, concision, and preservation of key information.

## Execution Boundaries

The main session asks the [orchestration runtime](../../skills/xc-orchestration-runtime/SKILL.md) for the next ready node or batch. For an opt-in leaf, the dispatch sequence is `next -> control-packet --node <id> -> start`. The main session reads the packet before starting or delegating the node, handles user gates, and verifies state after workers return.

Each worker executes exactly the packet's one target node. It reads only supplied inputs and references, writes the declared artifact, then calls `complete`, `fail`, or `block`. A worker does not inspect the complete tree, execute sibling work, use source IDs as authority to start other nodes, or decide the next global transition.

Long reports, diffs, and logs belong in artifacts. The blackboard contains short structured values that influence later scheduling or decisions.

## Scoped Handoffs

A leaf declares domain-named source categories, source and artifact thresholds, and any blackboard keys that may be projected. A direct `node:` selector identifies one source. A `bb:` selector reads a compact UTF-8 JSON array of terminal runtime leaf IDs, such as `["rt_source_a","rt_source_b"]`; it is not a CSV value, wildcard, or permission list. Lifecycle callers publish the actual terminal source IDs before requesting the packet and never substitute an ancestor or group ID.

The packet contains only the target leaf contract, declared source result fields and artifacts, selected blackboard scalars, local readiness blockers, and the permitted control action. It does not inherit ancestor declarations or expose undeclared sibling or future-node data, source instructions, undeclared artifacts, unselected blackboard keys, the complete blackboard, or the complete tree. A source ID grants evidence projection only, not authority over that source or any other node.

This boundary limits runtime protocol disclosure; it is not host mediation. The runtime cannot prevent an agent from using ordinary host tools before `start`, and it cannot enforce which identity actually invokes the CLI. Hosts and calling Skills must enforce those boundaries.

## Completion And Gates

Opt-in completion metadata can require non-empty `summary` or `validation`, artifact minimum and maximum counts, an exact literal or blackboard-selected artifact path, and declared normalized check receipts. `complete` accepts one repeated `--check-result-json` value per declared check. A receipt has the exact shape `{"schema_version":1,"check":"...","ok":true,"subject":"...","facts":{...}}`; the runtime validates its shape, declared name, `ok`, subject, and fact values, then stores only the normalized receipt.

The caller must actually run the declared validator, require a successful process exit and top-level success, and extract only its normalized receipt. The receipt is nevertheless unsigned, unbound caller self-report, not proof that validation ran or proof of who ran it. A fabricated receipt that exactly matches the declared structure and expected values is accepted. Runtime checks improve result consistency; they do not establish trusted execution.

An opt-in structured gate declares allowed lowercase-kebab outcomes, whether a non-empty decision is required, and optionally an outcome blackboard key. The main session completes it with `--gate-outcome` and, when required, `--decision`; the result and optional blackboard write occur atomically. A legacy gate without these declarations keeps its existing completion behavior.

The runtime validates and publishes an outcome but does not assign domain acceptance semantics to its spelling. Current lifecycle templates therefore route the published value through fail-closed topology: accepting outcomes select normal continuation; rejection, required revision, an unresolved clarification, or the reconciliation `revise-goal` outcome exposes an open recovery group and keeps implementation, verification, final validation, result writing, or finalization unavailable. The recovery group contains revision work and a successor gate that must publish an accepting value before continuation. An optional skipped gate uses its owning template's explicit safe default rather than an empty outcome.

## Resuming Work

Resume through the runtime's public commands using the existing tree reference. `next`, `summary`, `show`, and `find` expose the state needed by the main session without direct access to managed storage. Callers use paths and node IDs returned by the runtime rather than reconstructing them.

An open, reachable dynamic group with no children is reported as awaiting work. The main session must add the approved nodes or explicitly close the group; an empty ready list is not automatically a deadlock.

A successfully completed tree is sealed. Additional work requires an explicit user-approved reason and the runtime's reopen operation; ordinary execution does not append to a sealed historical tree.

## Failures And Recovery

- Use `fail` when a node attempted its work and could not satisfy its contract. Runtime preserves that current failure and its declared artifacts.
- When the same approved leaf contract should run again, the main session uses `retry-failed --reason <reason>` and may supply the current `--expected-revision`. Runtime archives the failed attempt before restoring scheduling; successful or running sibling work is not reset.
- When scope, acceptance, ownership, or side effects must change, add alternate recovery work or use a gate instead of retrying the old contract.
- Use `block` when progress depends on user input, external access, a safe reproduction prerequisite, or another recoverable condition.
- Treat verification failures as results. Do not alter behavior or acceptance criteria inside a verification node merely to obtain a pass.
- Report state conflicts, sealed-tree responses, and integrity failures to the main session instead of retrying an ambiguous mutation.
- Use runtime diagnostics and explicit integrity repair operations. Never repair checksums or status fields directly.

Archived attempts remain visible through node queries and their artifacts remain visible through `artifacts`. Conditions cannot silently replace a failure; they are reevaluated only after explicit retry. Engine-generated switch and loop failures are not failed executable attempts and need a different recovery decision.

When runtime checkpoint commits are enabled, terminal transitions and declared workshop artifacts are path-scoped. A failed checkpoint restores the tree transition, so an uncommitted persistence error is not reported as successful completion. `retry-failed` persists immediately as a non-terminal mutation and enters the next checkpoint.
