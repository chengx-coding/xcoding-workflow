# Milestone User Gates

Main-session discipline for user gates that activate at user-visible milestone boundaries in long work orders. Works with `jit-milestone-protocol.md`; the gate shape is declared by `assets/jit-milestone-flow.json` and built into `assets/jit-milestone-template.xml`.

## Activation

A milestone acceptance gate activates when the milestone work group completes and its evidence thresholds are established. The gate asks exactly one focused approval question; it does not collect evidence itself.

## Gate Contract

- Executor: main session. Outcomes `approved|revision-required`, `decision_required=true`, outcome published atomically to `milestone.accepted`.
- Control packet categories declared on the gate:
  - `milestone-evidence`: selectors `bb:milestone.evidence_sources`, `min_sources=1`, `artifact_min=1`.
  - `demo-evidence`: selectors `bb:milestone.demo_sources`, `min_sources=1`, `artifact_min=1`.
- The gate can only run after evidence-artifact-producing leaves are declared as sources in both blackboard keys.

## Main-Session Ordering

1. Collect demo evidence first: run outputs, screenshots, and test results, each recorded as a declared node artifact.
2. Publish `bb:milestone.demo_sources` with the terminal evidence-leaf IDs; the same leaves may also appear in `milestone.evidence_sources`.
3. Request the gate control packet and verify both categories resolve before proceeding.
4. Start the gate and ask one focused approval question; record the answer as the gate decision.

## Outcomes

- `approved`: start the finalizer only after this outcome is published; the main session MUST verify the packet resolves before completing the finalizer.
- `revision-required`: do not start the finalizer. Revision work reuses the recovery patterns from `recovery-patterns.md` — P3 (Rescope) with P2 (Alternate Approach) mechanics, as detailed in `jit-milestone-protocol.md` lifecycle step 5.

## Rules

- Evidence gaps and acceptance conditions trigger reviewed dynamic subtrees or recovery work; they are never silently skipped.
- Keep blackboard values short. Demo evidence itself is an artifact; only the source leaf IDs live on the blackboard.
- Pacing limits optional depth only; it never removes the gate, the finalizer, or the evidence thresholds.
