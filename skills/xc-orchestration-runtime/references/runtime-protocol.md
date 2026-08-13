# Runtime Protocol

`xc-orchestration-runtime` operates managed `schema_version="1"` runtime trees. Agents use the required `xcoding runtime` CLI and never directly inspect or edit runtime XML.

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
retry-failed         Archive a failed leaf attempt and return it to scheduling.
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
restore-point        Capture, list, or restore workshop-scoped restore points.
archive-subtree      Archive a succeeded or closed subtree into the read-only archived registry.
```

All commands return JSON. `--json` is accepted for host compatibility.
`complete`, `fail`, and `block` accept optional, repeatable `--artifact`
arguments:

```powershell
xcoding runtime fail `
  --tree <tree_ref> --node <node_id> --reason "<failure_reason>" `
  --artifact <first_path> --artifact <second_path>

xcoding runtime block `
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
- Only `task` and `gate` leaves can be started, completed, failed, blocked, unblocked, or retried.
- `start` uses the same core readiness predicate as `next`; possessing a runtime node ID does not bypass conditions, dependencies, ancestor state, or sequence ordering.
- `complete`, `fail`, and `block` require the target leaf to be `running`.
- `composite` and `loop` states are recalculated by the runtime.
- `succeeded` and `skipped` let parent scheduling continue.
- `failed` and `blocked` stop their enclosing sequence until handled. `retry-failed --reason` is the only failed-leaf transition back into ordinary scheduling.

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
node may become pending when the condition turns true. With
`when.policy=latched`, the runtime stores the first condition result reached
after dependency, ancestor, and sequence blockers clear; both true and false
results remain fixed for that runtime node instance. A loop iteration reset
clears descendant latches for the next iteration. Neither policy overwrites
`failed`; after an explicit `retry-failed`, reactive conditions reevaluate and
latched conditions retain the stored result for that node instance.

When a loop chooses break, natural completion, or its configured limit outcome,
the runtime stores that terminal decision and closes any nonterminal descendant
as `skipped` with `skip_reason=loop_closed`. Reloads and later blackboard writes
preserve the decision and cannot return a completed historical loop to running.

## Failed Attempt Recovery

`retry-failed` accepts only a failed executable task or gate leaf in a mutable
tree and requires a non-empty reason. The normal optional
`--expected-revision` rejects stale recovery decisions before mutation. It
archives the current attempt number, agent, start and failure timestamps,
failure result, declared artifacts, retry reason, and retry timestamp; then it
increments the current attempt, removes current execution fields and result,
and stabilizes the tree from that leaf upward. Succeeded or running sibling
branches are not reset.

`show`, `find`, and snapshots expose ordered archived attempts plus the current
attempt number. `artifacts` returns archived declarations in attempt order and
adds an `attempt` field for retry-aware entries; an un-retried attempt 1 keeps
the legacy response shape. Control packets advertise `retry-failed` for a
failed target, but source projection uses only the current terminal result,
not archived attempts.

This is controlled repetition of the same executable-leaf contract. It is not
automatic retry policy, backoff, a budget, replacement work, supersession, or
recovery for switch and loop failures generated by the engine.

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

When `auto_commit=true`, `complete`, `fail`, and `block` create terminal checkpoints. Each checkpoint includes the managed tree and every declared `--artifact` path in one path-scoped workshop commit. A non-terminal mutation that newly seals the root is also a completion checkpoint. Every newly sealed checkpoint includes the generated complete-tree SVG beside `orchestration.xml`. Declared checkpoint artifacts must exist inside the same workshop Git repository as the tree. Rendering, writing, or commit failure restores the pre-operation XML and SVG bytes; a rejected commit returns `persisted_uncommitted`, and the terminal state, revision, and declarations are not accepted. When `auto_commit=false`, checkpoint creation and checkpoint path validation are disabled; the terminal state, declarations, and newly sealed SVG are persisted without a workshop commit. `init`, `start`, `set`, `add-node`, `embed-subtree`, `unblock`, and `retry-failed` otherwise persist state but defer commit creation to the next checkpoint.

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
xcoding runtime repair-integrity --tree <tree_ref> --reason "<reason>"
```

The repair operation validates structure, restores managed metadata, recalculates the canonical checksum, reloads the written tree, and follows configured workshop-commit rules. A failed workshop commit returns `persisted_uncommitted`; recovery validates existing artifacts and retries or reconciles through the runtime rather than directly editing the tree.

## Restore Points

`restore-point` manages workshop-scoped recovery snapshots stored next to the
runtime tree:

```text
restore-point create  --tree TREE [--name NAME]
restore-point list    --tree TREE
restore-point restore --tree TREE --restore-point ID --reason REASON [--expected-revision N]
```

`create` validates tree integrity and structure, then writes
`<runtime_dir>/restore-points/<id>/` containing `manifest.json` (id,
created_at, name, tree sha256, and a per-file artifact sha256 list), a
canonical copy of `orchestration.xml`, and copies of every declared terminal
artifact. Declared artifacts must exist and resolve inside the same workshop
Git repository as the tree. `list` enumerates restore points with metadata in
deterministic order.

`restore` verifies every stored manifest checksum fail closed (mismatch or a
missing stored file aborts before any mutation), writes the stored tree bytes
over the live tree, restores stored artifact copies to their declared paths,
recomputes integrity metadata, records an auditable restore epoch with the
reason, and persists through the existing path-scoped checkpoint rules. A
sealed successful tree accepts restore with an explicit non-empty reason;
restore is never silent, and restoring a sealed snapshot re-seals the tree.
`--expected-revision` guards optimistic restores with `state_conflict` before
any mutation. Stable failures are `restore_point_not_found`,
`restore_point_invalid_id`, `restore_point_checksum_mismatch`,
`restore_point_file_missing`, `restore_point_path_violation`, and
`restore_point_manifest_invalid`. The runtime revision remains monotonic
across restores.

## Subtree Archiving

`archive-subtree` retires a completed subtree from active scheduling while
preserving its complete record inside the managed tree:

```text
archive-subtree --tree TREE --subtree NODE --reason REASON [--expected-revision N]
```

Eligibility requires the subtree root to be `succeeded` or a `closed` dynamic
group. The runtime root node is never archiveable, and the subtree must not
contain running leaves, ready leaves (including pending leaves that the
readiness predicate would schedule), archived stubs (nested archiving is
refused so every live stub keeps its own registry record), or dependency
targets of live nodes outside the subtree; each refusal uses a stable error
code: `archive_node_not_found`, `archive_root_refused`,
`archive_status_refused`, `archive_running_leaf`, `archive_ready_leaf`,
`archive_dependency_target`, `archive_nested_archived_stub`, and
`archive_reason_required`. Refusals are read-only.

The live tree replaces the subtree root with an `archived` stub that keeps
the node identity (`id`, `template_id`, `role`, `title`, type metadata) plus
`archived_at`, `archived_reason`, `archived_revision`, and an
`archived.record_id` pointer. The full original node — children, results,
checks, and declared artifacts — is stored as a serialized record in the
managed tree's `archived_subtrees` registry, so the existing canonical
checksum covers archived history.

Registry consistency is enforced symmetrically: every registry entry must
have a matching live archived stub, and every archived stub's
`archived.record_id` must have a matching registry entry. `validate` fails
on either direction. `repair-integrity` restores a recordless stub's entry
deterministically when the registry holds exactly one record whose root node
id equals the stub id; any other recordless stub is rejected with the stable
`archived_stub_record_missing` diagnostic instead of guessing.

Archived stubs are read-only history: they are never ready and never appear
in `ready`/`next` batches, sequence predecessors treat them as completed,
and `add-node`, `embed-subtree`, `close-group`, and `reopen-group` refuse
them with `archived_stub_read_only`. `summary` reports `archived_subtrees`
and excludes archived stubs from active `counts`. `show` and `find` surface
the archived record with its audit metadata for archived stubs, and
`artifacts` keeps terminal artifact paths declared inside archived records
discoverable with `archived: true`.

`--reason` is required and recorded. The mutation follows ordinary
path-scoped checkpoint rules (deferred commit like `retry-failed`, with
automatic promotion when archiving newly seals the root), and a stale
`--expected-revision` returns `state_conflict` before any mutation.
