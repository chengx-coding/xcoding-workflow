# Recovery Patterns for Main Sessions

Compact recovery library for main-session decisions about failed, blocked, or gate-rejected work. Choose exactly one pattern per incident, based on whether the accepted contract still holds and who owns the required change. All runtime operations named here are part of the public runtime contract.

## P1 — Retry Same Leaf

- **Trigger**: a leaf reported `failed`; the approved node contract — solution, inputs, acceptance criteria, ownership, and side effects — is unchanged; the cause is transient or worker-level, not a contract defect.
- **Allowed runtime operations**: `retry-failed --node <leaf> --reason <reason>`, passing `--expected-revision` when available. The runtime archives the failed result, artifacts, agent, and timestamps under an immutable attempt record, increments the attempt number, and returns only that leaf to scheduling.
- **Required evidence/artifacts**: the failed attempt's recorded summary and artifact; confirmation that the accepted contract is unchanged; a reason string stating why another execution is safe.
- **Prohibitions**: editing the old contract, adding or removing nodes, resetting successful or running siblings, manual state repair, and retrying engine-generated composite or loop failures (not eligible).

## P2 — Alternate Approach

- **Trigger**: the goal stands but the solution, acceptance criteria, ownership, or side effects must change; executing the old contract again is no longer appropriate.
- **Allowed runtime operations**: `reopen-group --reason` when the owning dynamic group is closed, then `add-node --before <blocked-child>` to insert explicitly approved recovery nodes; publish the revised plan and source IDs through `set` or a terminal operation's `--set`; `unblock` the original leaf so it continues, records a no-op, or rolls back before successor nodes run.
- **Required evidence/artifacts**: a revised plan artifact, re-published source keys, and a recorded statement of what changed and why.
- **Prohibitions**: silently mutating the old contract, unblocking the child before the recovery node publishes the new plan, and erasing failed-attempt history.

## P3 — Rescope

- **Trigger**: the selected solution needs revision — an approval gate returned `rejected` or `revision-required`, or the rescope itself is a material human decision.
- **Allowed runtime operations**: keep continuation blocked; open `solution-recovery-group`, add a revision node and a successor approval gate; the successor gate must atomically publish `approved` through its `--gate-outcome` before consequential work continues; record the decision as structured gate state.
- **Required evidence/artifacts**: collected evidence presented at the gate, a focused question whose answer is recorded as structured state, and the revised solution artifact.
- **Prohibitions**: continuing successor work before the successor gate publishes `approved`, bypassing the owning user gate, and downgrading an explicitly managed decision to an implicit one.

## P4 — Escalate

- **Trigger**: an unresolved external prerequisite or an unsafe rollback blocks progress, and none of P1–P3 can proceed safely.
- **Allowed runtime operations**: keep the node blocked via `block --reason`, open a main-session user gate (`executor=main`), present collected evidence, and ask one focused question; the recorded answer may authorize a later recovery pattern.
- **Required evidence/artifacts**: the blocker's collected evidence, the focused question, and the recorded decision.
- **Prohibitions**: speculative unblocks, silently skipping the blocker, further mutation beyond diagnostics, and inventing evidence to force a route.

## Selection

Pick the lowest pattern that satisfies the incident: P1 when only execution failed; P2 when the approach changed but the solution remains workflow-owned; P3 when solution selection or scope needs human revision; P4 when neither evidence nor safety permits another pattern. Escalation is never a failure; it is a governed state.

`scripts/recovery_plan.py` is the deterministic helper that translates one selected pattern and the incident state into the exact ordered runtime command sequence and required evidence; it executes nothing and touches no tree.
