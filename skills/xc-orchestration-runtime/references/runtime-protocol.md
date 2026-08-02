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
init                 Instantiate a managed template in a workbench runtime path.
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
control-packet        Return one leaf's explicitly declared scoped packet.
snapshot             Export the viewer JSON model.
integrity-status     Report access policy and checksum state.
repair-integrity     Explicitly restore managed metadata after a mismatch.
validate             Validate a managed runtime tree or template.
```

All commands return JSON. `--json` is accepted for host compatibility.
`complete`, `fail`, and `block` accept optional, repeatable `--artifact`
arguments:

```powershell
python "$SKILL_DIR/scripts/orchestration.py" fail `
  --tree <tree_ref> --node <node_id> --reason "<failure_reason>" `
  --artifact <first_path> --artifact <second_path>

python "$SKILL_DIR/scripts/orchestration.py" block `
  --tree <tree_ref> --node <node_id> --reason "<block_reason>" `
  --artifact <evidence_path>
```

Write responses include a monotonic `revision`. A caller MAY include
`--expected-revision <value>` in a later write; a mismatch returns
`state_conflict`. The runtime serializes local cross-process writes regardless
of whether a caller supplies that optimistic precondition.

## Node and State Rules

- Runtime IDs are generated as `rt_<work_order_id>__<instance_id>__<template_id>`.
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

Dynamic nodes may receive scalar `metadata.*` attributes through repeated `add-node --metadata metadata.<key>=value` arguments. Artifact-producing nodes use `metadata.artifact.audience` (`internal` by default) and `metadata.artifact.content_language` (`en` by default). A user-facing artifact declares `audience=user` and `content_language=work_order.document_language`; its writer resolves that selector before writing document frontmatter.

Use `artifacts --audience user` to locate previously declared user-facing reports for a language correction. The response includes only paths declared by terminal `complete`, `fail`, or `block` operations, their owner node IDs, and `metadata.artifact.*`; it never discovers files by scanning directories.

## Scoped Control Packets

A `task` or `gate` leaf opts in with one or more complete category declarations:

```text
metadata.control_packet.category.<lowercase-kebab-name>.selectors=["node:RUNTIME_ID","bb:KEY"]
metadata.control_packet.category.<lowercase-kebab-name>.min_sources=NON_NEGATIVE_INTEGER
metadata.control_packet.category.<lowercase-kebab-name>.artifact_min=NON_NEGATIVE_INTEGER
metadata.control_packet.blackboard_keys=["selected.key"]
```

Arrays are compact JSON. Selectors expand in declaration order; `bb:` source
lists are non-empty JSON arrays of unique runtime IDs and expand in array
order. Categories are returned by name. Every source must exist, be terminal,
and expose a summary, gate outcome, decision, failure reason, or block reason.
Duplicate selectors and duplicate expanded IDs fail; sources shared by
different categories remain allowed. Category source and artifact thresholds
are generic declaration values.

`control-packet --tree TREE --node NODE` never inherits ancestor metadata and
never returns siblings, descendants, a full blackboard, source instructions,
or undeclared artifacts. It returns the target fields, declared source result
projection, selected blackboard scalars, local readiness blockers, and the
current control action. Target and source projections include their runtime
`role` and immutable `logical_key` so domain validators can bind declared
evidence to a planned semantic node without reading the full tree. Missing declarations return
`control_packet_not_declared`; unsatisfied selectors or thresholds return
`control_packet_unavailable` without changing the revision.

## Completion and Gates

Completion declarations use:

```text
metadata.completion.required_fields=["summary","validation"]
metadata.completion.artifacts.min=0
metadata.completion.artifacts.max=1
metadata.completion.artifacts.path=bb:KEY|literal:VALUE
metadata.completion.checks=["xc-document"]
metadata.completion.check.<name>.subject=bb:KEY|literal:VALUE
metadata.completion.check.<name>.facts.<field>=bb:KEY|literal:VALUE
```

`complete` accepts repeated `--check-result-json` values with the exact shape
`{"schema_version":1,"check":"...","ok":true,"subject":"...","facts":{...}}`.
Each receipt is limited to 8192 UTF-8 bytes; receipt names are unique, facts
contain only JSON scalars, and no extra fields are accepted. The runtime stores
only normalized receipts. It compares them with declared names, subjects, and
facts, but does not execute or import a domain validator. Receipts are
unsigned, unbound self-reports, so a fabricated structurally matching receipt
is accepted. Malformed receipts return `invalid_check_result`; unmet
completion declarations return `completion_requirements_failed`. Rejection is
atomic, and `fail` and `block` do not apply success requirements.

Structured gates declare a non-empty unique lowercase-kebab
`metadata.gate.outcomes` array, an explicit
`metadata.gate.decision_required=true|false`, and an optional valid
`metadata.gate.outcome_key`. Opt-in gates require `--gate-outcome`; required
decisions use `--decision`. Publishing an outcome and its blackboard key is one
terminal mutation, and a simultaneous `--set` of that key returns
`gate_outcome_conflict`. Runtime gate structure still does not authenticate
the CLI caller.

The three recognized metadata prefixes fail closed with
`invalid_control_metadata` for unknown keys, invalid owners, malformed values,
or incomplete declarations. Unknown metadata outside those prefixes remains
allowed. Nodes without these declarations preserve schema-version-1 command
and result shapes.

When `auto_commit=true`, `complete`, `fail`, and `block` create terminal checkpoints. Each checkpoint includes the managed tree and every declared `--artifact` path in one path-scoped workshop commit. A non-terminal mutation that newly seals the root is also a completion checkpoint. Every newly sealed checkpoint includes the generated complete-tree SVG beside `orchestration.xml`. Declared checkpoint artifacts must exist inside the same workshop Git repository as the tree. Rendering, writing, or commit failure restores the pre-operation XML and SVG bytes; a rejected commit returns `persisted_uncommitted`, and the terminal state, revision, and declarations are not accepted. When `auto_commit=false`, checkpoint creation and checkpoint path validation are disabled; the terminal state, declarations, and newly sealed SVG are persisted without a workshop commit. `init`, `start`, `set`, `add-node`, `embed-subtree`, and `unblock` otherwise persist state but defer commit creation to the next checkpoint.

When the root succeeds, the runtime records `sealed_at` and rejects ordinary
writes with `tree_sealed`. `reopen --reason` is an explicit main-session
operation: it records a new epoch before further dynamic work can be appended.
Domain workflows must collect the required user decision before reopening. A
newly sealed root writes `<normalized-work-order-name>.svg` beside the runtime XML.
The SVG contains every node regardless of Viewer collapse state. Reopening
preserves the last successful SVG; the next successful seal overwrites it.

## Viewer Behavior

The loopback Viewer serves retained runtime snapshots only. Its page requests
the selected snapshot every 20 seconds and skips rendering when the snapshot
version is unchanged. Manual forced refresh remains available.

The graph viewport has a draggable lower boundary and exposes synchronized
wheel and range-slider zoom. The SVG download endpoint renders the same
complete snapshot model used for automatic terminal export.

The native tree picker requires the actual bound loopback Host and a matching
browser Origin when Origin is present. The Viewer serializes picker requests
and launches a helper process so Tk owns the dialog on that process's main
thread. The helper does not open a console window on Windows. A concurrent
picker request is rejected while the first dialog is active. Cancellation is
not an error. A selected file is validated and only its parent directory is
added to the Viewer allow roots. The existing direct path registration
endpoint does not expand allow roots.

## Integrity and Recovery

Read operations return integrity details after direct edits are detected. Normal writes reject non-valid integrity. Use:

```powershell
python "$SKILL_DIR/scripts/orchestration.py" repair-integrity --tree <tree_ref> --reason "<reason>"
```

The repair operation validates structure, restores managed metadata, recalculates the canonical checksum, reloads the written tree, and follows configured workshop-commit rules. A failed workshop commit returns `persisted_uncommitted`; recovery validates existing artifacts and retries or reconciles through the runtime rather than directly editing the tree.
