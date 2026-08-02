---
name: "xc-work"
description: "Classifies governance, plans proportional managed effort, or runs full and adaptive managed work orders for investigation, iteration, repair, review, maintenance, or cross-feature work without implicitly creating a feature."
---

# XC Work

`xc-work` is the common lifecycle, governance, and proportional-effort entry point for existing-code work. Its default `run` operation preserves the full durable work-order lifecycle. `adaptive-run` opens the same durable workbench but creates only the nodes, documents, gates, and verification capabilities required by an approved plan. The read-only `classify` and `plan` operations create no managed state. A work order may reference no feature, one existing feature, or multiple existing features.

## Parameters

- `operation` - `enum`; optional, defaults to `run`
  - Allowed values: `run`, `classify`, `plan`, `adaptive-run`.
  - Scope: Selects the full managed lifecycle, governance classifier, read-only effort planner, or minimal adaptive managed lifecycle.

- `workshop_path` - `path`; required for `operation=run|adaptive-run`, omitted for `operation=classify|plan`
  - Scope: The fixed project `.xcoding` workshop used only by the managed lifecycle.

- `project_root` - `path`; required for `operation=run|adaptive-run`, omitted for `operation=classify|plan`
  - Scope: Business repository root supplied to `xc-open-work-order`.

- `request` - `string`; required
  - Scope: Requested investigation, change, repair, review, or maintenance outcome.

- `feature_ids` - `string[]`; optional for `operation=run|adaptive-run`
  - Scope: Existing related feature identifiers. An empty list is valid.

- `mode` - `enum`; optional for `operation=run|plan|adaptive-run`, defaults to `change`
  - Allowed values: `investigation`, `change`, `repair`, `review`, `maintenance`.
  - Scope: Controls default analysis, solution, implementation, and verification gates. The runtime blackboard remains authoritative for the selected execution path.

- `document_language` - `string`; optional for `operation=run|adaptive-run`
  - Scope: Explicit simplified BCP 47 language tag for top-level work order documents. When omitted, use the initiating user request's clearly dominant language; if that cannot be decided quickly, use `en`.

- `scope` - `enum`; optional for `operation=plan|adaptive-run`, defaults to `unknown`
  - Allowed values: `single-location`, `module`, `cross-cutting`, `unknown`.
- `clarity` - `enum`; optional for `operation=plan|adaptive-run`, defaults to `unknown`
  - Allowed values: `exact`, `known-root`, `uncertain`, `unknown`.
- `risk` - `enum`; optional for `operation=plan|adaptive-run`, defaults to `unknown`
  - Allowed values: `low`, `medium`, `high`, `unknown`.
- `verification` - `enum`; optional for `operation=plan|adaptive-run`, defaults to `unknown`
  - Allowed values: `focused`, `regression`, `multi-environment`, `unknown`.
- `coordination` - `enum`; optional for `operation=plan|adaptive-run`, defaults to `unknown`
  - Allowed values: `single`, `review`, `multi-party`, `unknown`.
- `duration` - `enum`; optional for `operation=plan|adaptive-run`, defaults to `unknown`
  - Allowed values: `single-step`, `multi-step`, `cross-session`, `unknown`.
- `audit` - `enum`; optional for `operation=plan|adaptive-run`, defaults to `unknown`
  - Allowed values: `runtime-only`, `result`, `full`, `unknown`.
- `pace` - `enum`; optional for `operation=plan|adaptive-run`, defaults to `adaptive`
  - Allowed values: `adaptive`, `fast`, `thorough`.
- `bridge_policy` - `enum`; optional for `operation=plan|adaptive-run`, defaults to `unknown`
  - Allowed values: `none`, `commit`, `review`, `approval`, `full`, `unknown`.
  - Scope: Normalized minimum retained evidence and decision policy from the applicable project bridge.

- `needs_persistence` - `enum`; optional for `operation=classify|plan|adaptive-run`
  - Allowed values: `no`, `yes`, `unknown`.
  - Scope: Whether correct completion requires durable state, recoverable progress, durable documents, or evidence usable beyond the current response.

- `material_impact` - `enum`; optional for `operation=classify|plan|adaptive-run`
  - Allowed values: `no`, `yes`, `unknown`.
  - Scope: Whether the work changes shared code, public contracts, user data, permissions, production or infrastructure state, security boundaries, or release assets.

- `difficult_rollback` - `enum`; optional for `operation=classify|plan|adaptive-run`
  - Allowed values: `no`, `yes`, `unknown`.
  - Scope: Whether a complete, lossless, verified one-step recovery is unavailable or the work has an irreversible external side effect.

- `crosses_sessions` - `enum`; optional for `operation=classify|plan|adaptive-run`
  - Allowed values: `no`, `yes`, `unknown`.
  - Scope: Whether completion requires another session, restart, scheduled wait, asynchronous external result, or cross-run recovery.

- `multiple_actors` - `enum`; optional for `operation=classify|plan|adaptive-run`
  - Allowed values: `no`, `yes`, `unknown`.
  - Scope: Whether at least two independent people, agents, approvers, or external systems own coordinated decisions or deliverables.

- `audit_required` - `enum`; optional for `operation=classify|plan|adaptive-run`
  - Allowed values: `no`, `yes`, `unknown`.
  - Scope: Whether the user, law, project bridge, Skill, or workflow contract requires retained traceability, approval, verification, review, or a commit.

## Classification Operation

`operation=classify` uses confirmed facts, not guesses from task length, model capability, or request wording. Determine each fact from the following objective evidence:

- `needs_persistence=yes` when correct completion writes or retains project or external state, durable documents, recoverable progress, or evidence usable after the current response. Use `no` only when no durable state is written and the result is consumed in the current interaction; otherwise use `unknown`.
- `material_impact=yes` when shared code, a public contract, user data, permissions, production or infrastructure state, a security boundary, or a release asset changes. Use `no` only for confirmed read-only work or an isolated temporary transformation with none of those effects; otherwise use `unknown`.
- `difficult_rollback=yes` when there is no confirmed, verified, lossless one-step recovery or an irreversible external side effect exists. Use `no` only for read-only work or a confirmed deterministic one-step full recovery; otherwise use `unknown`.
- `crosses_sessions=yes` when the request requires a later session, restart, scheduled wait, asynchronous external result, or cross-run recovery. Use `no` only when all inputs are available for one continuous execution with no wait or resume requirement; otherwise use `unknown`.
- `multiple_actors=yes` when at least two independent people, agents, approvers, or external systems own coordinated decisions or deliverables. Use `no` only for one actor with no approval, handoff, or parallel dependency; otherwise use `unknown`.
- `audit_required=yes` when the user, law, project bridge, Skill, or workflow contract requires retained traceability, approval, verification, review, or a commit. Use `no` only after reading applicable policy and confirming that none requires it; otherwise use `unknown`.

Interpret evidence using the established priority of host and security rules, explicit user requirements, the project bridge, public Skill contracts, and observable task facts. An unresolved conflict becomes `unknown`; never infer `no` from silence or model judgment.

Before confirming the vector, read the applicable `.xcoding/WORKFLOW.md` when project context is expected. A bridge may only tighten facts: `no` may become `unknown` or `yes`, and `unknown` may become `yes`. It must not change `yes` or `unknown` to `no`, or `yes` to `unknown`. If the expected bridge is missing or an applicable rule cannot be read, set at least `audit_required=unknown`.

Invoke the executable public adapter, passing each available fact at most once:

```text
python skills/xc-work/scripts/classify.py \
  [--needs-persistence no|yes|unknown] \
  [--material-impact no|yes|unknown] \
  [--difficult-rollback no|yes|unknown] \
  [--crosses-sessions no|yes|unknown] \
  [--multiple-actors no|yes|unknown] \
  [--audit-required no|yes|unknown]
```

The adapter fills omitted facts with `unknown`, invokes the bundled strict low-level classifier with all six flags, and validates its JSON, schema, route, facts, unknowns, triggers, and escalation. Only six `no` values return `route=direct`; any `yes` or `unknown` returns `route=managed`. Successful results preserve the low-level ordered `triggers`, `facts`, and `unknowns`.

Classification permits only evidence collection needed to confirm the six facts, including the applicable bridge read. It creates no workshop, work order, document, runtime tree, artifact, or commit and performs no substantive project or external action.

The public adapter always exits zero with a JSON object. A missing executable, timeout, low-level nonzero exit, unparseable output, unknown schema or route, invalid output, or malformed, duplicate, or contradictory public input becomes this successful fail-closed result instead of an empty, direct, or process-error result:

```json
{"schema_version":1,"ok":true,"route":"managed","classification_status":"escalated","reason_codes":["classification-unavailable"],"escalation":{"entry_point":"xc-work"},"diagnostic":{"input_error":"<stable-error-code>"}}
```

`scripts/classify.py` is the public lifecycle trust boundary. It guarantees deterministic managed escalation for adapter-observable input and subprocess failures, but it does not authenticate the caller, interpreter, executable bytes, or host, and it provides no host mediation or attestation. `scripts/classify_governance.py` remains a strict nonzero-exiting diagnostic tool; lifecycle callers must not invoke it in place of the adapter or interpret its failures themselves.

When the route is managed, invoke public `xc-work operation=run` with the original request and applicable managed parameters. During direct execution, re-confirm all six facts before the next substantive action whenever new evidence appears. If the route becomes managed or classification becomes unavailable, invoke `operation=run` with the original request, completed actions, and current evidence before continuing.

## Planning Operation

`operation=plan` computes the minimum sufficient managed shape without creating a work order. Read the project bridge first, submit the same six governance facts used by classification, normalize its delivery requirements into `bridge_policy`, and supply the observable task facts. Do not infer favorable values from task length, file count, model capability, or confidence.

Invoke the public adapter:

```text
python skills/xc-work/scripts/plan_work.py \
  --request <request> \
  --bridge-sha256 <sha256> \
  --needs-persistence no|yes|unknown \
  --material-impact no|yes|unknown \
  --difficult-rollback no|yes|unknown \
  --crosses-sessions no|yes|unknown \
  --multiple-actors no|yes|unknown \
  --audit-required no|yes|unknown \
  --bridge-policy none|commit|review|approval|full|unknown \
  --scope single-location|module|cross-cutting|unknown \
  --clarity exact|known-root|uncertain|unknown \
  --risk low|medium|high|unknown \
  --verification focused|regression|multi-environment|unknown \
  --coordination single|review|multi-party|unknown \
  --duration single-step|multi-step|cross-session|unknown \
  --audit runtime-only|result|full|unknown \
  --pace adaptive|fast|thorough \
  --mode investigation|change|repair|review|maintenance
```

The strict policy merges capability contributions by Boolean OR, minimum implementation units by `max`, verification scopes by stable ordered union, and depth by `max`. Governance and bridge facts establish a floor before task facts. Read-only modes never acquire mutation-only capabilities during fail-closed escalation. `fast` uses the required minimum and cannot remove required work; `thorough` may add analysis, review, recovery exercise, and regression depth. Missing or invalid public input, a low-level failure, or forged output returns the mode-appropriate full safe capability set.

The plan receipt binds the request, bridge bytes, normalized facts, capabilities, counts, depth, and an ordered `required_nodes` manifest. Before the first adaptive implementation node starts, validate the receipt by rerunning the strict policy:

```text
python skills/xc-work/scripts/validate_plan_receipt.py \
  --receipt-json <compact-receipt> \
  --request <original-request> \
  --bridge <project-.xcoding/WORKFLOW.md>
```

Before starting the plan-specific finalizer, build a source map from its scoped packet and validate exact required-node coverage:

```text
python skills/xc-work/scripts/validate_adaptive_manifest.py \
  --receipt-json <compact-receipt> \
  --source-map-json <logical-key-to-terminal-source-map>
```

The manifest validator rejects missing, extra, duplicate, stale, failed, blocked, wrong-role, insufficient-artifact, or missing-verification-scope records and returns the exact source and artifact thresholds for the finalizer.

## Adaptive Run Operation

`operation=adaptive-run` is an explicit opt-in managed lifecycle. Omitted `operation` and `operation=run` retain the full existing lifecycle and document behavior.

1. Read `AGENTS.md`, `.xcoding/WORKFLOW.md`, and `.xcoding/KNOWLEDGE.md`, validate feature IDs, open the work order, fix its document language, and compute a validated plan.
2. Initialize `assets/adaptive-work-order-template.xml`. Its static topology is only the root and one open sequence `work-group`.
3. Before starting any leaf, add every initial plan-required node and a plan-specific finalizer, publish source keys, then close the group. A minimal mutation uses one combined implementation/focused-verification worker plus the finalizer.
4. Embed the plan receipt and request scope in the first worker's immutable node metadata or inputs. Existing solution and approval source rules still apply whenever those capabilities are enabled.
5. Add top-level work-order documents only when their capability is true. Runtime node results and one compact node artifact are sufficient for a minimal workbench.
6. Build the dynamic sequence in this order when selected: goal, analysis or diagnosis, clarification, solution, approval, implementation units, verification scopes, independent review, result, finalizer.
7. The dynamic finalizer declares actual required source IDs and plan-specific source/artifact thresholds. Empty work groups and missing required evidence must not finalize.

The combined minimal worker may perform one coherent edit and focused verification. If scope, cause, risk, ownership, duration, or verification expands, block before further mutation. Reopen a closed group when needed, insert re-planning or recovery before the blocked direct child, publish the new plan, then unblock the original leaf to continue or record a no-op/rollback before successor nodes run. An unsafe rollback or unresolved external prerequisite remains blocked and uses a main-session gate.

Adaptive work has no global node ceiling. Each loop remains bounded, while reviewed dynamic subtrees and recovery groups may be added as evidence requires. A user-requested fast pace limits optional depth only; it never removes required acceptance, verification, approval, audit, or recovery.

## Run Operation

Omitting `operation` or specifying `operation=run` preserves the existing managed behavior. It never invokes classification or downgrades to direct, even when all six facts would be `no`.

1. Read `AGENTS.md`, `.xcoding/WORKFLOW.md`, and `.xcoding/KNOWLEDGE.md`.
2. Verify every supplied `feature_id` already exists. Do not create or adopt a feature.
3. Call `xc-open-work-order`, initialize `assets/work-order-template.xml`, determine and validate `work_order.document_language` through `xc-document`, then complete `prepare-work-order`. An explicit `document_language` wins; otherwise use only the initiating request's clearly dominant language or `en`.
4. Create `goal.md` through document evolution. Before every top-level work order document subtree, set `document.content_language` to `work_order.document_language`. Set blackboard controls based on the requested mode and required gates.
5. When analysis is needed, schedule `xc-analysis` nodes and synthesize accepted evidence into `analysis.md`.
6. When feature IDs are present, embed `xc-feature-reconciliation` sequentially under `reconciliation-group` before selecting a work order solution.
7. When evidence leaves a material human-owned decision unresolved, or the user explicitly asks to clarify or stress-test work, set `work_order.requires_clarification=true` and embed `xc-clarify` under `clarification-group`. The group must complete before selecting a solution.
8. Create `solution.md` when a change strategy must be selected. Publish the terminal solution writer ID as the compact JSON array in `work_order.solution_source_ids`, read the approval control packet, and complete `approve-work-order-solution` with `--gate-outcome approved|rejected|revision-required` plus a non-empty decision. The default `work_order.solution_gate_outcome=approved` is used only when the optional gate is skipped. A rejected, revision-required, or otherwise non-approved value opens `solution-recovery-group` and keeps the approved continuation closed. Add revision and a successor approval gate inside that recovery group; the successor gate must atomically publish `approved` before consequential work can continue.
9. Add approved implementation nodes through `xc-implementation`, then verification nodes through `xc-verification` only after `approved-solution-continuation` is selected. Publish each node's declared source IDs through its node-specific blackboard key before requesting its control packet; do not substitute ancestor or group IDs.
10. Create `result.md` through document evolution. Publish the terminal goal writer ID in `work_order.objective_source_ids` and the terminal result writer ID in `work_order.result_source_ids`, read the finalizer control packet, and complete `finalize-work-order`.

When `next` or `summary` reports `awaiting_dynamic_groups`, the main session
must append the planned subtree or explicitly close an intentionally empty
group before treating the work order as blocked. An explicit correction to a
successful work order first passes through the owning user gate and runtime `reopen`;
ordinary work must not append to a sealed historical tree.

## Runtime Source Publication

Control-packet source keys contain UTF-8 compact JSON arrays of terminal runtime leaf IDs and are written only through runtime `set` or a terminal operation's `--set`. The solution, objective, and result keys select document writer leaves because those leaves declare the durable document artifacts. Dynamic implementation and verification nodes use the node-specific keys and metadata defined by their owning Skills. If a declared source is unavailable, non-terminal, or semantically insufficient, do not invent a reference or weaken the threshold; schedule the missing work or block the consumer leaf.

## Mode Rules

- `investigation`: normally requires analysis and result, but may skip solution, implementation, and verification.
- `review`: normally requires analysis and review artifacts, but does not modify reviewed inputs.
- `repair`: uses `xc-diagnosis` when root cause is uncertain, then follows the regular solution, implementation, and verification path.
- `change` and `maintenance`: select only the documents and nodes necessary for the requested outcome.

## Reconciliation and Concurrency

Work orders may analyze and design for the same feature concurrently. Before any baseline modification, the active work order re-checks feature provenance and warns when another work order changed the baseline. The workflow does not use feature locks or leases. Users coordinate the serialized timing of actual feature baseline modifications.

## Constraints

- An ordinary work order never implicitly creates `.xcoding/features/<feature-id>/`.
- Code and executable tests are evidence of current behavior; feature baselines are approved target intent. Ambiguous conflict requires a user gate.
- Dynamic state, task ordering, retry state, and blockers remain in the runtime tree, not in documents.
- Governance routing is independent of model name, model vendor, context-window size, environment labels, and project technology stack. The same confirmed fact vector always produces the same route.
- Do not re-detect language from later user messages. A user may explicitly correct `work_order.document_language`; revise already declared top-level work order documents and `metadata.artifact.audience=user` reports through runtime-managed document-evolution work.
