# JIT Milestone Decomposition Protocol

Compact main-session protocol for large managed work orders whose top-level tree keeps milestones only. Each milestone subtree is grown just-in-time when the milestone starts. `assets/jit-milestone-template.xml` is the runtime shape; all operations below are public runtime commands.

## Template Shape

The instantiated milestone subtree contains exactly:

- `milestone-group`: open `role=dynamic-group` sequence under the work-order root.
- `milestone-work-group`: open `role=dynamic-group` sequence inside it; implementation, review, and verification leaves are appended here.
- `milestone-acceptance-gate`: `gate executor=main` with structured outcomes `approved|revision-required`, `decision_required=true`, `outcome_key=milestone.accepted`, and an evidence-scoped control packet.
- `milestone-finalizer`: `task executor=main` following the gate; it carries the same evidence-scoped control packet and only runs after the gate publishes `approved`.

## Invariants

- The minimal tree is a legal prefix of the maximal workflow. All growth is additive (`add-node`, `embed-subtree`, `reopen-group`); escalation never discards completed work and never rewrites accepted contracts.
- Before the first milestone leaf starts, all initial leaves AND the plan-specific finalizer with evidence thresholds MUST exist. The static finalizer exists from `init`; its thresholds live in `milestone.evidence_sources` (compact JSON array of terminal leaf IDs) plus the declared `min_sources` and `artifact_min`. Publish `milestone.evidence_sources` with `set` before starting the first leaf. The finalizer's control packet is an advisory evidence projection: it reports unresolved until the threshold is met, and completion does not reject it. The main session MUST verify the packet resolves before completing the finalizer; this discipline, with the finalizer starting only after `milestone.accepted == approved`, keeps a minimal tree from sealing before its evidence threshold is established.
- Evidence gaps and acceptance conditions trigger reviewed dynamic subtrees or recovery work; they are never silently skipped.

## Lifecycle

1. When a milestone starts, append its planned leaves to `milestone-work-group` with `add-node`. Publish the leaf source IDs to `milestone.evidence_sources` before the first leaf starts.
2. Execute leaves in sequence. `close-group` the work group when all planned leaves are appended.
3. When the work group completes, request the acceptance gate's control packet to assemble evidence, then start and complete the gate with `--gate-outcome approved` or `--gate-outcome revision-required` plus a recorded decision. The gate writes `milestone.accepted` atomically.
4. Start the finalizer only after `milestone.accepted == approved`. It validates the evidence sources and closes the milestone.
5. On `revision-required`: do not start the finalizer. Follow an adaptation of recovery-patterns.md P3 (Rescope) with P2 (Alternate Approach) mechanics: `reopen-group` the work group, append revision work and a successor acceptance gate that atomically publishes `approved` through its own `--gate-outcome`, then close the group and continue at step 4.

## Recovery Integration

Choose one pattern from `references/recovery-patterns.md` per incident:

- P1: a failed leaf with an unchanged contract uses `retry-failed --node <leaf> --reason`.
- P2: a changed approach uses `reopen-group`, then `add-node --before` to insert recovery nodes, publish the revised evidence keys, and unblock the original leaf.
- P3: a gate returning `revision-required` (or a rescope decision) keeps continuation blocked; revision work plus a successor gate that atomically publishes `approved` precede the finalizer.
- P4: an unresolved external prerequisite or unsafe rollback stays blocked via `block --reason` and opens a main-session user gate; the recorded answer authorizes a later pattern.

## Rules

- Use only documented runtime operations: `init`, `next`, `start`, `complete`, `fail`, `block`, `unblock`, `retry-failed`, `set`, `add-node`, `embed-subtree`, `close-group`, `reopen-group`, `summary`, `control-packet`. Do not invent commands or edit runtime XML directly.
- New milestone subtrees are appended beneath the top-level milestone list with `add-node` or `embed-subtree`; a completed milestone subtree is never rewritten.
- Keep the milestone blackboard to short control values (`milestone.accepted`, `milestone.evidence_sources`); long analysis and reports are artifacts.
- Pacing limits optional depth only; they never remove the gate, the finalizer, or the evidence threshold.
