**Language:** **English** | [简体中文](../zh-CN/orchestration/runtime-model.md)

# Runtime Model

The [`xc-orchestration-runtime` contract](../../skills/xc-orchestration-runtime/SKILL.md) defines a domain-neutral control plane for managed `schema_version="1"` trees. Agents operate it only through public commands.

## Objects and Identity

A template defines reusable structure. A runtime tree is one instantiated work order with node state, blackboard values, results, declared artifacts, loop history, provenance, revision, integrity, and sealing metadata.

Template nodes use stable kebab-case `template_id` values. Template-local dependencies use `local:<template_id>`. Instantiation rewrites them to runtime IDs:

```text
rt_<work_order_id>__<instance_id>__<template_id>
```

Each instantiated node retains `origin_template_id` and `origin_instance_id`. Dynamic callers provide a kebab-case `logical_key`; runtime generates the actual ID. Its incidental spelling is not a caller contract.

Embedded templates receive isolated instance namespaces and rewritten local references. They share the parent blackboard. Scoped blackboard translation, linked child work orders, and cross-process cancellation are not supported.

## Nodes and States

The four node types are:

- `composite`: a sequence, parallel group, switch, or dynamic group.
- `task`: an executable leaf.
- `gate`: an executable leaf handled by `executor=main`.
- `loop`: a bounded container with end-of-iteration decisions.

Executors are `main`, `subagent`, `tool`, and `service`. Runtime behavior depends on control fields such as `type`, `mode`, `executor`, `when`, and dependencies. Domain meaning belongs in `role`, `metadata.*`, and node text.

States are `pending`, `ready`, `running`, `succeeded`, `failed`, `blocked`, and `skipped`. `ready` is valid but is primarily computed. Only task and gate leaves can start or receive terminal updates. `complete`, `fail`, and `block` require `running`; `unblock` returns a blocked leaf to pending. `retry-failed` archives a failed task or gate attempt and returns that leaf to ordinary scheduling. Runtime computes composite and loop states.

`succeeded` and `skipped` satisfy progress. A failed or blocked descendant stops its enclosing sequence until the workflow handles it. Runtime provides explicit failed-leaf recovery, not automatic retry policy.

### Failed attempts

`retry-failed --node <id> --reason <reason>` accepts only a failed executable leaf in a mutable tree. It preserves the failed result, artifacts, agent, and timestamps as ordered attempt history, records the recovery reason, increments the current attempt, and recalculates ancestors without resetting successful or running siblings. Callers may supply `--expected-revision` to reject a stale decision.

`show`, `find`, and snapshots expose attempt history. `artifacts` continues to expose archived declarations and identifies retry-aware entries by attempt number while preserving the legacy shape for an un-retried attempt 1. A failed control-packet target advertises `retry-failed`; archived attempts do not become current source evidence.

Conditions never overwrite `failed`. They are evaluated normally only after explicit retry returns the leaf to scheduling. Switch no-match, multiple-match, and loop-limit failures are engine-generated container outcomes and are not eligible for this leaf operation.

Explicit retry repeats the same node contract. Automatic backoff, budgets, replacement work, supersession, and general container recovery are not runtime capabilities.

## Scheduling and Readiness

`next` stabilizes the tree and returns ready executable leaves, optionally limited as a batch. `start` applies the same readiness predicate. Knowing an ID never bypasses node status, conditions, dependencies, ancestor state, or sequence order.

- A sequence exposes its first incomplete reachable child.
- A parallel composite may expose multiple independent children.
- Explicit dependencies must have succeeded or skipped.
- Conditions support a truthy key, `!key`, equality, and inequality.
- `when.policy=reactive` is the default and can reopen a conditionally skipped node when its value changes.
- `when.policy=latched` makes that skip final for the template instance.

The runtime repeatedly applies condition and switch routing and bottom-up container aggregation until state is stable.

## Switches

A `mode=switch` composite reads `switch.key`. Exactly one matching `role=case` child, or a default child, is selected; other branches are skipped. Multiple matches fail. No match fails by default or may be configured as blocked.

Complex decisions should be computed by an earlier task and written as one short blackboard value. Switches route that value; they do not provide a general expression language.

## Dynamic Groups and Dependencies

A `role=dynamic-group` composite starts open unless explicitly closed by its template. `add-node` and `embed-subtree` can append work while it is open. A reachable empty open group appears in `awaiting_dynamic_groups`; the orchestrator must add work or call `close-group`. An empty closed group succeeds.

Closed groups reject ordinary additions. `reopen-group --reason` is an auditable recovery operation, and approved recovery work may be inserted with `add-node --before`. This is controlled recovery, not a generic retry mechanism.

Explicit dependencies add limited cross-tree edges, but the model remains tree-first. Authors should not use them to construct an opaque general DAG.

## Loops

Every loop has a positive `loop.max_iterations` and `loop.on_limit` of `failed`, `blocked`, or `succeeded`. After all children succeed or skip, runtime evaluates `loop.break_when` and `loop.continue_when`, records iteration history, and either exits, resets for another iteration, or applies the limit result.

Loop decisions happen at iteration boundaries. There are no `break-loop`, `continue-loop`, sibling-cancellation, subtree-termination, parent-completion, or run-abort control signals.

## Scoped Control Packets

A `task` or `gate` leaf may declare one or more domain-named `metadata.control_packet.category.*` categories. Each category supplies a compact JSON selector array, `min_sources`, and `artifact_min`. `node:<runtime-id>` selects one source; `bb:<key>` reads a blackboard scalar that must contain a non-empty compact JSON array of unique runtime IDs. Categories are domain-owned; runtime only validates names, expansion, terminal state, projectable result content, and thresholds.

`metadata.control_packet.blackboard_keys` is a separate compact JSON array of scalars to project. A blackboard key used to find source IDs is not exposed unless it is also explicitly selected. Declarations belong only to the target leaf: ancestors cannot declare, contribute, or override packet metadata.

`control-packet --node` returns the target contract, declared source projections, selected blackboard values, local blockers, and a control action. It never returns target children, source instructions, undeclared sibling or future-node data, unselected blackboard values, the full blackboard, undeclared artifacts, or the full tree. Sources can contribute only projected result fields: identity, title, role, status, summary, declared artifacts, structured gate outcome and decision, failure or block reason, and stored normalized checks.

Missing declarations return `control_packet_not_declared`. Invalid or unsatisfied selectors, sources, thresholds, or selected keys return `control_packet_unavailable` without a partial packet or revision change. A source ID provides evidence, not permission to start or mutate that node.

## Gates, Completion, Blackboard, and Artifacts

A gate is a main-session executable leaf. The main session gathers evidence, asks a focused question, and records the decision as structured state. Workers do not independently question the user.

An opt-in gate declares a unique lowercase-kebab outcome list, an explicit `decision_required` boolean, and optionally an outcome blackboard key. `complete --gate-outcome` records an allowed outcome; `--decision` supplies the required explanation. Result storage and the optional outcome-key update are atomic, and an explicit `--set` of the same key is rejected. Runtime validates the declaration and value but does not authenticate who invoked the CLI.

The runtime deliberately does not decide which domain outcomes are accepting. Domain flow specs use ordinary reactive conditions, switches, and dynamic groups to make that decision mechanical. Current lifecycle templates select consequential continuation only for explicit accepting values; every declared non-accepting value selects an open recovery branch, while an unknown switch value blocks. A successor recovery gate can atomically replace the outcome with an accepting value and reactivate the normal branch. Optional skipped gates use a domain-owned safe default declared in the canonical flow.

Opt-in completion metadata can require `summary` and `validation`, artifact cardinality and a literal or blackboard-selected artifact path, and normalized check receipts. Receipt shape, size, uniqueness, declared name, boolean success, subject, and scalar facts are validated before success; rejection leaves the tree and revision unchanged. `fail` and `block` do not apply success completion requirements.

A normalized receipt is untrusted caller self-report, not execution proof. It is unsigned and has no claimant binding or attestation. Runtime does not import or run a domain validator, so a fabricated receipt with an exact structural and expected-value match is accepted. A caller is still required to execute the validator, check its process and top-level result, and pass only the normalized receipt.

The blackboard holds short cross-node values. Dot-separated names are a convention, not a schema. Reports, plans, findings, logs, and generated content belong in artifacts.

Terminal operations may declare artifact paths. `artifacts` returns only those declarations and their metadata; it does not scan workshop directories or provide a standalone artifact index. Dynamic nodes can declare artifact audience and language metadata for later controlled discovery.

## Worker Protocol

The [single-node worker contract](../../skills/xc-orchestration-runtime/references/subagent-contract.md) uses split ownership:

1. The main session gets a ready node and, for an opt-in leaf, requests its control packet.
2. The main session starts the packet target and delegates only that node.
3. The worker executes exactly that node using the supplied packet, inputs, and references.
4. The worker writes durable outputs and calls `complete`, `fail`, or `block`.
5. The main session verifies runtime state.

A worker reports `state_conflict` or `tree_sealed` rather than retrying an ambiguous write. Failed means one execution attempt failed; blocked means a recoverable human, external, or environmental prerequisite is missing. Neither state is silently skipped. The main session may explicitly retry the same failed leaf contract; the worker does not retry itself.

## Transitions, Integrity, and Concurrency

Every write returns a monotonic revision. Callers may provide `--expected-revision`; a mismatch returns `state_conflict`. Runtime also serializes local cross-process writes, validates structure and integrity, performs atomic replacement with transient Windows retry, reloads the result, and verifies its checksum.

Managed trees contain an access policy and canonical SHA-256 integrity metadata. Reads report mismatches; ordinary writes require valid integrity. `repair-integrity --reason` is the explicit recovery operation. The checksum detects unmanaged edits but is not cryptographic authentication.

## Persistence, Checkpoints, and Sealing

Configuration precedence is explicit `--config`, then the nearest
`.xcoding/xc-orchestration-runtime.json`, then built-in defaults. JSON
configuration rejects duplicate keys, non-finite numbers, and non-object
roots. Explicit paths must end in `.json`. A discovered retired TOML file
produces migration guidance instead of silently using defaults; JSON and TOML
at the same discovery level are rejected as ambiguous.

### Migrate a legacy runtime configuration

To migrate an existing workshop:

1. Copy `skills/xc-orchestration-runtime/assets/xc-orchestration-runtime.json`
   to `.xcoding/xc-orchestration-runtime.json`.
2. Transfer customized values from TOML `[git]`, `[integrity]`, and `[viewer]`
   sections into the corresponding JSON objects. Preserve values such as
   `git.auto_commit`, the commit message, and a customized Viewer port.
3. Remove `.xcoding/xc-orchestration-runtime.toml` before running another
   runtime or Viewer command. Keeping both files is rejected as ambiguous.

The JSON shape is:

```json
{
  "schema_version": 1,
  "git": {
    "auto_commit": true,
    "commit_message": "chore(orchestration): {operation} {work_order_id} [{checksum_short}]",
    "on_commit_failure": "warn"
  },
  "integrity": {
    "algorithm": "sha256",
    "canonicalization": "orchestration-tree-v1",
    "on_mismatch_read": "warn",
    "on_mismatch_write": "block"
  },
  "viewer": {
    "host": "127.0.0.1",
    "port": 20668,
    "watch_interval_seconds": 1,
    "heartbeat_seconds": 15,
    "idle_shutdown_seconds": 120
  }
}
```

With `auto_commit=true`, terminal operations checkpoint the tree and declared artifacts in one path-scoped workshop commit. A checkpoint that newly seals the root also includes a complete standalone SVG. If rendering, writing, or committing fails, runtime restores the previous tree and SVG and returns `persisted_uncommitted`; the terminal transition and artifact declarations are not accepted.

With `auto_commit=false`, checkpoint commits and checkpoint path validation are disabled, while state and declarations still persist. Non-terminal mutations normally persist without a commit and enter the next checkpoint. `retry-failed` follows this non-terminal persistence model because the accepted failure and its artifacts were already checkpointed.

A successful root is sealed. Ordinary mutations then return `tree_sealed`. `reopen --reason` records a new epoch and requires the owning workflow's explicit user-approved reason. This is recovery of a completed tree, not routine continuation.

## Compatibility And Limits

Control packets, completion requirements, normalized receipts, and structured gates are opt-in extensions within `schema_version="1"`. Existing schema-version-1 nodes and gates without the corresponding metadata preserve their legacy command and result shapes. Earlier schema formats remain unsupported, and in-flight trees are not retrofitted by inferring leaf declarations from ancestors.

Scoped packets reduce runtime protocol disclosure, but runtime cannot prevent ordinary host-tool calls before a node is started and does not mediate host tools afterward. This version has no trusted validator execution, claim binding, typed blackboard, host mediation, or model-specific execution profile. Model capability does not expand packet scope or weaken managed controls.

Any reported `context_bytes` measurement counts normalized UTF-8 protocol payload bytes. It is not a token count and makes no claim about model latency, execution latency, cost, or output quality.

See the [runtime protocol](../../skills/xc-orchestration-runtime/references/runtime-protocol.md) for the public command contract.
