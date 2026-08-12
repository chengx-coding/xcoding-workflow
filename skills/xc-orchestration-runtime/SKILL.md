---
name: "xc-orchestration-runtime"
description: "Runs and observes managed orchestration trees. Invoke when a workflow needs scheduling, controlled node updates, integrity repair, snapshots, subtree embedding, or local viewing."
---

# XC Orchestration Runtime

`xc-orchestration-runtime` is the generic control plane for complex Agent workflows. It owns managed runtime trees, state transitions, scheduling, integrity, controlled persistence, snapshots, and the local viewer. It does not define domain tasks such as implementation, review, or testing.

## Implementation Ownership

The required `xcoding` package owns the runtime implementation under
`xcoding.runtime`:

- `core.py` owns the tree model, scheduling, integrity, locking and persistence primitives.
- `application.py` owns command use cases, read/write transactions, rollback and stable result/error mapping.
- `commands.py` owns the complete 23-command parser specification.
- `query.py` owns the typed nine-command read-only transport allowlist and parameter validation.

This Skill is not self-contained. Install the matching `xcoding` package
before using it. `scripts/orchestration.py` is a legacy executable adapter
that replaces itself with `xcoding runtime`; it owns no parser, runtime,
transaction, persistence, Viewer, or fallback implementation.

## Mandatory Boundaries

- Agents MUST NOT directly read, summarize, edit, patch, or reformat managed orchestration XML. Use this Skill's documented public runtime commands.
- The main session requests ready nodes, starts delegated work, handles `executor=main` gates, and checks summaries. It does not need the full tree.
- A worker executes exactly one assigned node and reports through `complete`, `fail`, or `block`.
- A known node ID is not start authority. `start` accepts only an executable leaf that satisfies the same readiness predicate used by `next`.
- Runtime trees use `schema_version="1"`. Earlier formats and CLI semantics are unsupported.
- A terminal operation is valid only for a `running` task or gate. A successful root is sealed until the main session explicitly reopens it after a user-approved reason.

## Runtime Lifecycle

```powershell
xcoding runtime init `
  --template <managed_template> `
  --runtime-path <workbench_runtime_path> `
  --work-order-id <work_order_id> `
  --name <work_order_name>

xcoding runtime next `
  --tree <tree_ref>

xcoding runtime start `
  --tree <tree_ref> --node <node_id> --agent <agent_id>

xcoding runtime complete `
  --tree <tree_ref> --node <node_id> `
  --summary "<summary>" --validation "<validation_result>" `
  --artifact <workshop_artifact_path>

xcoding runtime fail `
  --tree <tree_ref> --node <node_id> --reason "<failure_reason>" `
  --artifact <workshop_artifact_path>

xcoding runtime block `
  --tree <tree_ref> --node <node_id> --reason "<block_reason>" `
  --artifact <workshop_artifact_path>
```

`init` writes `<workbench_runtime_path>/orchestration.xml`. The work-order opener owns creation of the workbench and its runtime path. All commands emit JSON; `--json` is accepted for host compatibility.

The deprecated `python "$SKILL_DIR/scripts/orchestration.py" ...` form forwards
to the installed `xcoding runtime` executable. When `xcoding` is unavailable,
it returns `xcoding_unavailable`; it has no local fallback.

The prerelease package additionally exposes
`xcoding daemon serve --tree <runtime>`. It binds to `127.0.0.1`, requires the
launch result's process-lifetime bearer token and exact Host/Origin checks,
accepts only launch-time runtime files, and exposes typed read-only queries
plus bounded non-durable summary SSE. It provides no runtime mutation, replay,
journal, remote bind, discovery, service installation, auto-start, or default
transport switch.

`--artifact` is optional and repeatable on `complete`, `fail`, and `block`.

Additional commands are `fail`, `block`, `unblock`, `retry-failed`, `set`, `add-node`,
`embed-subtree`, `close-group`, `reopen-group`, `reopen`, `summary`, `show`,
`find`, `artifacts`, `control-packet`, `snapshot`, `integrity-status`,
`repair-integrity`, and `validate`. `control-packet --node` returns only the
target leaf's declared sources, selected blackboard values, readiness blockers,
and control projection. `reopen-group --reason` is an auditable recovery
operation for a closed dynamic group. `add-node --before` may then insert
explicitly approved recovery work before a blocked direct child.

`retry-failed --node <failed-leaf> --reason <reason>` is the explicit recovery
operation for one failed task or gate attempt. It archives the failed result,
artifacts, agent, and timestamps under an immutable attempt record, increments
the attempt number, and returns only that leaf to ordinary scheduling.
`--expected-revision` provides the normal optimistic concurrency guard.
Condition handling resumes only after this explicit transition; reactive nodes
reevaluate, while latched nodes retain their stored instance result. Conditions
never overwrite a failed node by themselves. Engine-generated composite and
loop failures are not eligible.

For `when.policy=latched`, the first condition result reached after dependency,
ancestor, and sequence blockers clear is stored on that runtime node. Loop
iteration reset clears descendant latches for the next iteration. A loop's
break, natural-completion, or limit decision is stored atomically with its
terminal status; nonterminal descendants close as `skipped` with
`skip_reason=loop_closed`, and later blackboard changes cannot reopen the loop.

An unreachable or otherwise non-runnable start returns `node_not_ready` with a
stable `details.reason` and does not change node state or runtime revision.
Condition, dependency, ancestor status, and sequence-predecessor blockers use
the same core readiness predicate as scheduler output. Stale expected
revisions remain `state_conflict`; successful sealed trees remain
`tree_sealed`.

`add-node` accepts repeated `--metadata metadata.<key>=value` values for dynamic node metadata. Use `metadata.artifact.audience=internal|user` and `metadata.artifact.content_language=en|work_order.document_language` to declare an artifact's audience and language selector. `artifacts --audience user` lists only paths declared through terminal `complete`, `fail`, or `block` operations and their node metadata; it never scans the workshop repository.

The runtime fail-closes recognized `metadata.control_packet.*`,
`metadata.completion.*`, and `metadata.gate.*` declarations during template
validation, initialization, and dynamic node creation. Other `metadata.*`
remains domain-owned. Control packets are leaf-only and never inherit ancestor
metadata. Opt-in completion may require fields, artifact cardinality and path,
and normalized `--check-result-json` receipts. Receipts are untrusted caller
self-reports: exact structural matches are accepted even when fabricated.
Opt-in gates require a declared `--gate-outcome` and may require `--decision`
while atomically publishing an outcome key.

Every write response returns a monotonic `revision`. Callers MAY pass it back as `--expected-revision <value>` on a later write; a mismatch returns `state_conflict`. The runtime serializes writes for one local tree even when callers omit that option.

`next` and `summary` return `awaiting_dynamic_groups` when a reachable, empty dynamic group is open. The main session must append work or call `close-group`; a closed group rejects further additions. Do not treat an empty `ready` list with awaiting groups as an unclassified deadlock.

## Persistence and Workshop Commits

Every managed tree has an access warning, access policy, and canonical SHA-256 integrity metadata. Normal writes reject invalid integrity; only `repair-integrity` can repair it after explicit inspection.

When `auto_commit=true`, each terminal node operation (`complete`, `fail`, or `block`) creates a path-scoped workshop commit containing both the tree transition and all declared `--artifact` paths. A commit failure restores the pre-operation tree and returns `persisted_uncommitted`; declared files remain available for recovery, but the terminal state and declarations are not accepted. When `auto_commit=false`, checkpointing and its path validation remain disabled, while the terminal state and artifact declarations are persisted in the tree. `init`, `start`, `set`, `add-node`, `embed-subtree`, `unblock`, and `retry-failed` normally persist state without a commit; their changes are included by the next terminal checkpoint. Archived attempt artifacts remain discoverable through `artifacts`, whose retry-aware entries include the owning attempt number while preserving the legacy shape for an un-retried attempt 1. A non-terminal mutation that newly seals the root is promoted to a completion checkpoint.

When the root succeeds, the runtime records sealing metadata and rejects ordinary mutations. `reopen --reason "<user-approved-reason>"` is the only mutation that can reopen a successful tree; it records a new epoch. Domain Skills must require an explicit main-session user decision before invoking it.

When a mutation newly seals the root, the runtime also writes a complete
standalone SVG beside `orchestration.xml`. Its filename is the normalized work-order
name with an `.svg` suffix. A successful completion after `reopen` overwrites
the same SVG. Every newly sealed checkpoint includes the SVG in the same
path-scoped commit and restores the previous XML and SVG bytes when rendering,
writing, or committing fails.

Declared commit artifacts MUST exist inside the same workshop Git repository as the runtime tree. The runtime never stages unrelated workshop changes. A failed commit returns `persisted_uncommitted`; files remain available for recovery, but the caller MUST treat the checkpoint as uncommitted.

Configuration is loaded in this order:

```text
CLI --config
> nearest .xcoding/xc-orchestration-runtime.json found upward from the tree
> builtin defaults
```

Use `assets/xc-orchestration-runtime.json` as the configuration starting
point. Configuration parsing rejects duplicate object keys, non-finite
numbers, and non-object roots. An explicit `--config` path must use `.json`.
Automatic discovery fails with migration guidance when it finds only the
retired `xc-orchestration-runtime.toml`, and fails as ambiguous when JSON and
TOML files coexist at the same discovery level; it never silently falls back
from a legacy file to builtin defaults.

Runtime identity uses `work_order_id`, lifecycle language uses
`work_order.document_language`, and workbench locations use the documented
target paths. Ordinary `orchestration.py` commands expose no alternate managed
identity fields, path forms, aliases, or fallback discovery.

## Viewer Interface

```powershell
xcoding runtime snapshot --tree <tree_ref>
xcoding viewer --tree <tree_ref>
```

The viewer consumes only runtime snapshots, binds to loopback, and exposes no
tree mutation endpoints. The page checks the selected snapshot every 20
seconds, supports a vertically resizable graph, synchronized wheel and slider
zoom, complete SVG download, and a native local XML picker. Direct path
registration remains constrained to Viewer allow roots; an explicit native
selection authorizes only the selected file's parent directory. Picker
requests require the actual bound loopback Host and matching browser Origin.
The server serializes requests and launches Tk in a helper process whose main
thread owns the dialog. On Windows, the helper starts without a console
window. A concurrent picker request is rejected while one dialog is active.

The default launch mode starts a detached background server and returns one
JSON result containing `ok`, `mode`, `pid`, `url`, and `trees`. The background
server does not write logs. Pass `--foreground` to keep the server in the
current terminal; it emits JSON-line lifecycle, client, and refresh events for
manual diagnostics. Pass `--no-browser` for automated verification. Use
`xc-orchestration-viewer` for user-facing open, monitor, or visualize
requests.

The package-owned Viewer is distinct from the daemon. It owns a browser UI,
Viewer-local registry, native picker, refresh controls, and SVG download; it
does not share the daemon bearer token or registry. Neither surface exposes
runtime mutation.

## References

- `assets/xc-orchestration-runtime.json`: configuration template.
- `references/runtime-protocol.md`: public runtime protocol.
- `references/subagent-contract.md`: single-node worker contract.
- `references/subtree-embedding.md`: embedded template protocol.
