# Runtime Protocol

`xc-orchestration-runtime` operates managed `schema_version="1"` runtime trees. Agents use `scripts/orchestration.py` and never directly inspect or edit runtime XML.

## Main Session Loop

```text
init
repeat:
  next
  start and delegate each ready subagent node
  handle main-executor gates
  receive complete, fail, or block updates
  summary
until status is complete, failed, or blocked
```

`next` returns ready executable leaves only. The main session consumes their JSON payload rather than reading the complete tree.

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
summary / show       Read progress or one node.
snapshot             Export the viewer JSON model.
integrity-status     Report access policy and checksum state.
repair-integrity     Explicitly restore managed metadata after a mismatch.
validate             Validate a managed runtime tree or template.
```

All commands return JSON. `--json` is accepted for host compatibility.

## Node and State Rules

- Runtime IDs are generated as `rt_<run_id>__<instance_id>__<template_id>`.
- A runtime node preserves `origin_template_id` and `origin_instance_id`.
- Dynamic nodes use a caller-provided kebab-case `logical_key`; the runtime assigns the real ID.
- Only `task` and `gate` leaves can be started, completed, failed, blocked, or unblocked.
- `composite` and `loop` states are recalculated by the runtime.
- `succeeded` and `skipped` let parent scheduling continue.
- `failed` and `blocked` stop their enclosing sequence until handled.

## Blackboard, Artifacts, and Checkpoints

Use the blackboard only for short control values such as `review.open_issues=false`. Rich reports, review findings, validation outputs, diagnostics, and generated documents are artifacts. The workflow does not create generic raw-log artifacts.

When `auto_commit=true`, `complete`, `fail`, and `block` create terminal checkpoints. A `complete` checkpoint includes the managed tree and every declared `--artifact` path in one path-scoped context commit. Declared checkpoint artifacts must exist inside the same context Git repository as the tree. `start`, `set`, `add-node`, `embed-subtree`, and `unblock` persist tree state but defer commit creation to the next checkpoint.

## Integrity and Recovery

Read operations return integrity details after direct edits are detected. Normal writes reject non-valid integrity. Use:

```powershell
python "$SKILL_DIR/scripts/orchestration.py" repair-integrity --tree <tree_ref> --reason "<reason>"
```

The repair operation validates structure, restores managed metadata, recalculates the canonical checksum, reloads the written tree, and follows configured context-commit rules. A failed context commit returns `persisted_uncommitted`; recovery validates existing artifacts and retries or reconciles through the runtime rather than directly editing the tree.
