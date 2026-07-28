# Runtime Protocol

`xc-orchestration-runtime` operates managed `schema_version="1"` runtime trees. Agents use `scripts/orchestration.py` and never directly inspect or edit runtime XML.

## Main Session Loop

```text
init
repeat:
  next
  append work to, or close, any awaiting dynamic group
  start and delegate each ready subagent node
  handle main-executor gates
  receive complete, fail, or block updates
  summary
until status is complete, failed, or blocked
```

`next` returns ready executable leaves and `awaiting_dynamic_groups`. An empty
`ready` list is not a deadlock when one of those groups is reachable: the main
session appends work or closes the group through the runtime.

## Commands

```text
init                 Instantiate a managed template in a run runtime directory.
next                 Return ready nodes.
start                Mark a ready task or gate as running without a checkpoint commit.
complete             Mark a task or gate successful and record outputs.
fail / block         Record a terminal failure or external blocker.
unblock              Return a blocked leaf to pending without a checkpoint commit.
set                  Update short cross-node blackboard values without a checkpoint commit.
add-node             Add a dynamic node using a logical_key.
embed-subtree        Instantiate a managed template under a runtime parent.
close-group          Close a dynamic group and reject future appends to it.
reopen               Reopen a sealed successful tree with an auditable reason.
summary / show / find Read progress, one node, or nodes with a template ID.
artifacts            List only terminally declared artifact paths and node metadata.
snapshot             Export the viewer JSON model.
integrity-status     Report access policy and checksum state.
repair-integrity     Explicitly restore managed metadata after a mismatch.
validate             Validate a managed runtime tree or template.
```

All commands return JSON. `--json` is accepted for host compatibility.

Write responses include a monotonic `revision`. A caller MAY include
`--expected-revision <value>` in a later write; a mismatch returns
`state_conflict`. The runtime serializes local cross-process writes regardless
of whether a caller supplies that optimistic precondition.

## Node and State Rules

- Runtime IDs are generated as `rt_<run_id>__<instance_id>__<template_id>`.
- A runtime node preserves `origin_template_id` and `origin_instance_id`.
- Dynamic nodes use a caller-provided kebab-case `logical_key`; the runtime assigns the real ID.
- Only `task` and `gate` leaves can be started, completed, failed, blocked, or unblocked.
- `start` uses the same core readiness predicate as `next`; possessing a runtime node ID does not bypass conditions, dependencies, ancestor state, or sequence ordering.
- `complete`, `fail`, and `block` require the target leaf to be `running`.
- `composite` and `loop` states are recalculated by the runtime.
- `succeeded` and `skipped` let parent scheduling continue.
- `failed` and `blocked` stop their enclosing sequence until handled.

When a mutable tree contains an executable leaf that is not currently ready,
`start` returns `node_not_ready`. Its `details.reason` is one of:

```text
node_status
condition_false
dependency_incomplete
ancestor_skipped
ancestor_failed
ancestor_blocked
ancestor_condition_false
ancestor_dependency_incomplete
sequence_predecessor_incomplete
```

The details may also identify the blocking node, its status, or incomplete
dependency IDs. A conditionally skipped node or ancestor uses the condition
reason; an unselected switch ancestor uses `ancestor_skipped`. Rejection is
read-only: the node status and runtime revision do not change. Mutation-level
guards run first, so stale `--expected-revision` remains `state_conflict` and a
successful sealed tree remains `tree_sealed`.

Nodes with `when` default to `when.policy=reactive`, so a conditionally skipped
node may become pending when the condition turns true. A template may set
`when.policy=latched` to make a conditional skip final for that instance.

A `role=dynamic-group` composite defaults to `dynamic.state=open`. An empty
open group is reported as awaiting. `close-group` changes the state to closed;
an empty closed group succeeds and `add-node` or `embed-subtree` then return
`group_closed`.

## Blackboard, Artifacts, and Checkpoints

Use the blackboard only for short control values such as `review.open_issues=false`. Rich reports, review findings, validation outputs, diagnostics, and generated documents are artifacts. The workflow does not create generic raw-log artifacts.

Dynamic nodes may receive scalar `metadata.*` attributes through repeated `add-node --metadata metadata.<key>=value` arguments. Artifact-producing nodes use `metadata.artifact.audience` (`internal` by default) and `metadata.artifact.content_language` (`en` by default). A user-facing artifact declares `audience=user` and `content_language=run.document_language`; its writer resolves that selector before writing document frontmatter.

Use `artifacts --audience user` to locate previously declared user-facing reports for a language correction. The response includes only paths declared by `complete --artifact`, their owner node IDs, and `metadata.artifact.*`; it never discovers files by scanning directories.

When `auto_commit=true`, `complete`, `fail`, and `block` create terminal checkpoints. A `complete` checkpoint includes the managed tree and every declared `--artifact` path in one path-scoped context commit. Declared checkpoint artifacts must exist inside the same context Git repository as the tree. `init`, `start`, `set`, `add-node`, `embed-subtree`, and `unblock` persist tree state but defer commit creation to the next checkpoint.

When the root succeeds, the runtime records `sealed_at` and rejects ordinary
writes with `tree_sealed`. `reopen --reason` is an explicit main-session
operation: it records a new epoch before further dynamic work can be appended.
Domain workflows must collect the required user decision before reopening.

## Integrity and Recovery

Read operations return integrity details after direct edits are detected. Normal writes reject non-valid integrity. Use:

```powershell
python "$SKILL_DIR/scripts/orchestration.py" repair-integrity --tree <tree_ref> --reason "<reason>"
```

The repair operation validates structure, restores managed metadata, recalculates the canonical checksum, reloads the written tree, and follows configured context-commit rules. A failed context commit returns `persisted_uncommitted`; recovery validates existing artifacts and retries or reconciles through the runtime rather than directly editing the tree.
