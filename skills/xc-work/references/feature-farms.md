# Feature-Farm Coordination

Compact main-session pattern for large parallel work inside one work order. A feature farm runs multiple independent milestone or feature subtrees in parallel under one work order, coordinated by the main session. Use it when confirmed scope splits into independent workstreams that must land as one governed work order.

## Definition

- A farm is a set of independent milestone or feature subtrees scheduled in parallel under one work-order root.
- Independence means no subtree consumes another subtree's runtime output; cross-subtree facts flow only through the blackboard, artifacts, or the main session.
- The main session owns the farm: it opens subtrees, batches scheduling, collects terminal results, and runs the integration node.

## Scheduling

- Host the farm subtrees in dynamic groups running in parallel mode. Each subtree inside its group follows its own protocol (see Consistency).
- Batch by declared dependencies: subtrees whose dependencies are terminal are scheduled in one batch; the rest wait. Dependency-aware batching never weakens declared readiness.
- A worker still executes exactly one node. Parallelism comes from multiple scheduled workers, never from one worker running several leaves.

## Blackboard Discipline

- Shared keys carry short control values only; long analysis and reports are artifacts.
- When the same shared key must be reused across farm instances, serialize the instances or give each instance a namespaced key; concurrent writers must not interleave on one key.
- Source IDs use node-specific keys such as `implementation.sources.<logical-key>` and `verification.sources.<logical-key>`. Do not substitute ancestor or group IDs.

## Integration Node

- After all farm subtrees complete, the main session runs an integration node that collects the terminal results of the subtrees.
- The node reconciles each result against the approved solution and feature baselines before recording it as work-order output.
- Conflicts that stay inside the approved solution or baseline intent may be resolved explicitly; incompatible evidence is never merged silently. Unsupported claims may be discarded; contradicting evidence may not.

## Conflict Escalation

- An ambiguous conflict — drift, product-intent conflict, or concurrent baseline modification — goes to a main-session user gate with the collected evidence and one focused question. This matches the xc-analysis rule: ambiguous conflict requires a user gate.

## Consistency

- Growth, prefix, and evidence-threshold invariants: `jit-milestone-protocol.md`. Each farm subtree is grown just-in-time and obeys the milestone prefix/growth rules.
- Farm subtree failure handling: `recovery-patterns.md`. Choose exactly one pattern per incident (P1-P4) before touching sibling subtrees.

## Rules

- Use only documented runtime operations: `init`, `next`, `start`, `complete`, `fail`, `block`, `unblock`, `retry-failed`, `set`, `add-node`, `embed-subtree`, `close-group`, `reopen-group`, `summary`, `control-packet`. Do not invent commands or edit runtime XML directly.
- Pacing limits optional depth only; it never removes required acceptance, verification, or evidence thresholds.
- A farm subtree is scheduled only when its declared readiness holds; failed or blocked subtrees go through recovery patterns, never skipped silently.
