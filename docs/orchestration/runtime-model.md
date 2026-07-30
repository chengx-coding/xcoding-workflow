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

States are `pending`, `ready`, `running`, `succeeded`, `failed`, `blocked`, and `skipped`. `ready` is valid but is primarily computed. Only task and gate leaves can start or receive terminal updates. `complete`, `fail`, and `block` require `running`; `unblock` returns a blocked leaf to pending. Runtime computes composite and loop states.

`succeeded` and `skipped` satisfy progress. A failed or blocked descendant stops its enclosing sequence until the workflow handles it. There is no generic `failed -> pending` retry command or automatic retry policy.

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

## Gates, Blackboard, and Artifacts

A gate is a main-session executable leaf. The main session gathers evidence, asks a focused question, and records the decision as structured state. Workers do not independently question the user.

The blackboard holds short cross-node values. Dot-separated names are a convention, not a schema. Reports, plans, findings, logs, and generated content belong in artifacts.

Terminal operations may declare artifact paths. `artifacts` returns only those declarations and their metadata; it does not scan workshop directories or provide a standalone artifact index. Dynamic nodes can declare artifact audience and language metadata for later controlled discovery.

## Worker Protocol

The [single-node worker contract](../../skills/xc-orchestration-runtime/references/subagent-contract.md) uses split ownership:

1. The main session gets a ready node and starts it.
2. The worker executes exactly that node using supplied inputs and references.
3. The worker writes durable outputs and calls `complete`, `fail`, or `block`.
4. The main session verifies runtime state.

A worker reports `state_conflict` or `tree_sealed` rather than retrying an ambiguous write. Failed means execution failed; blocked means a recoverable human, external, or environmental prerequisite is missing. Neither state is silently skipped.

## Transitions, Integrity, and Concurrency

Every write returns a monotonic revision. Callers may provide `--expected-revision`; a mismatch returns `state_conflict`. Runtime also serializes local cross-process writes, validates structure and integrity, performs atomic replacement with transient Windows retry, reloads the result, and verifies its checksum.

Managed trees contain an access policy and canonical SHA-256 integrity metadata. Reads report mismatches; ordinary writes require valid integrity. `repair-integrity --reason` is the explicit recovery operation. The checksum detects unmanaged edits but is not cryptographic authentication.

## Persistence, Checkpoints, and Sealing

Configuration precedence is explicit `--config`, then the nearest `.xcoding/xc-orchestration-runtime.toml`, then built-in defaults.

With `auto_commit=true`, terminal operations checkpoint the tree and declared artifacts in one path-scoped workshop commit. A checkpoint that newly seals the root also includes a complete standalone SVG. If rendering, writing, or committing fails, runtime restores the previous tree and SVG and returns `persisted_uncommitted`; the terminal transition and artifact declarations are not accepted.

With `auto_commit=false`, checkpoint commits and checkpoint path validation are disabled, while state and declarations still persist. Non-terminal mutations normally persist without a commit and enter the next checkpoint.

A successful root is sealed. Ordinary mutations then return `tree_sealed`. `reopen --reason` records a new epoch and requires the owning workflow's explicit user-approved reason. This is recovery of a completed tree, not routine continuation.

See the [runtime protocol](../../skills/xc-orchestration-runtime/references/runtime-protocol.md) for the public command contract.
