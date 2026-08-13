# Decision Registry

Append-only decision record for managed work orders. The registry stores durable reasoning for material decisions so later nodes, reviewers, and resuming sessions can replay why a choice was made. It is pure file state: `decision_registry.py` owns every read and write, and the file format is append-only JSONL.

## Activation Policy

- Activation conditions are owned by the project bridge (`.xcoding/WORKFLOW.md`) and the planning policy, not by this reference. The registry activates only when bridge or planner policy says so.
- When the planner activates the registry, it records the fact triggers that justify activation in the work order. Suggested triggers:
  - `duration=cross-session`: the work or its consequences span more than one session.
  - `risk=high`: decisions materially affect correctness, security, or rollback.
  - `audit=full`: the work order requires a full audit trail.
  - `coordination=multi-party`: multiple actors or features share the affected surface.
- The bridge may tighten these triggers; it MUST NOT relax them. A missing bridge rule fails closed to planner policy.

## Recording

- Record every material decision when it is made: the chosen option, why, and the evidence behind it.
- One JSONL line per decision with exactly these fields: `id`, `work_order_id`, `timestamp` (UTC ISO-8601), `decision`, `rationale`, `evidence_refs`, `actor`.
- `id` is unique inside one registry file; a duplicate id is rejected with a stable error. Never reuse an id across retries of the same logical decision.
- `evidence_refs` lists artifact or source identifiers that back the decision. Use short structured identifiers, not report content.

## Consulting

- Before an architecture-level choice (interfaces, file and state formats, cross-feature coupling, governance-significant trade-offs), replay the registry with `list` and `get` and read the relevant prior decisions.
- Reuse a recorded decision only when the same facts still hold. A changed bridge, feature baseline, or confirmed fact invalidates reuse and requires a new decision.
- The registry is read-only after write: no update or delete command exists. Corrections are new decisions whose `rationale` or `evidence_refs` reference the superseded id.

## Command Surface

- `decision_registry.py record --path P --work-order-id W --decision-id D --decision X --rationale R --evidence-refs '["a","b"]' --actor A [--timestamp UTC-ISO]`
- `decision_registry.py list --path P` — deterministic replay sorted by timestamp then id.
- `decision_registry.py get --path P --decision-id D`

All failures report `ok:false` with a stable error code and never modify the file.
