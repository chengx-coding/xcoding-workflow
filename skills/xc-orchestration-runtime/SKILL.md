---
name: "xc-orchestration-runtime"
description: "Runs and observes managed orchestration trees. Invoke when a workflow needs scheduling, controlled node updates, integrity repair, snapshots, subtree embedding, or local viewing."
---

# XC Orchestration Runtime

`xc-orchestration-runtime` is the generic control plane for complex Agent workflows. It owns managed runtime trees, state transitions, scheduling, integrity, controlled persistence, snapshots, and the local viewer. It does not define domain tasks such as implementation, review, or testing.

## Mandatory Boundaries

- Agents MUST NOT directly read, summarize, edit, patch, or reformat managed orchestration XML. Use `scripts/orchestration.py` only.
- The main session requests ready nodes, starts delegated work, handles `executor=main` gates, and checks summaries. It does not need the full tree.
- A worker executes exactly one assigned node and reports through `complete`, `fail`, or `block`.
- Runtime trees use `schema_version="1"`. Earlier formats and CLI semantics are unsupported.

## Runtime Lifecycle

```powershell
python "$SKILL_DIR/scripts/orchestration.py" init `
  --template <managed_template> `
  --runtime-dir <run_runtime_dir> `
  --run-id <run_id> `
  --name <run_name>

python "$SKILL_DIR/scripts/orchestration.py" next `
  --tree <tree_ref>

python "$SKILL_DIR/scripts/orchestration.py" start `
  --tree <tree_ref> --node <node_id> --agent <agent_id>

python "$SKILL_DIR/scripts/orchestration.py" complete `
  --tree <tree_ref> --node <node_id> `
  --summary "<summary>" --validation "<validation_result>" `
  --artifact <context_artifact_path>
```

`init` writes `<run_runtime_dir>/orchestration.xml`. The run-creation capability owns creation of `<run_runtime_dir>` and its parent run directory. All commands emit JSON; `--json` is accepted for host compatibility.

Additional commands are `fail`, `block`, `unblock`, `set`, `add-node`, `embed-subtree`, `summary`, `show`, `snapshot`, `integrity-status`, `repair-integrity`, and `validate`.

## Persistence and Context Commits

Every managed tree has an access warning, access policy, and canonical SHA-256 integrity metadata. Normal writes reject invalid integrity; only `repair-integrity` can repair it after explicit inspection.

When `auto_commit=true`, `init`, template operations, and each terminal node operation create a path-scoped context commit. A terminal `complete` commit contains both the tree transition and all declared `--artifact` paths. `start`, `set`, `add-node`, `embed-subtree`, and `unblock` persist state without a commit; their changes are included by the next terminal checkpoint.

Declared commit artifacts MUST exist inside the same context Git repository as the runtime tree. The runtime never stages unrelated context changes. A failed commit returns `persisted_uncommitted`; files remain available for recovery, but the caller MUST treat the checkpoint as uncommitted.

Configuration is loaded in this order:

```text
CLI --config
> nearest .xcoding/xc-orchestration-runtime.toml found upward from the tree
> builtin defaults
```

Use `assets/xc-orchestration-runtime.toml` as the configuration starting point.

## Viewer Interface

```powershell
python "$SKILL_DIR/scripts/orchestration.py" snapshot --tree <tree_ref>
python "$SKILL_DIR/scripts/viewer_server.py" --tree <tree_ref>
```

The viewer consumes only runtime snapshots, binds to loopback, and exposes no tree mutation endpoints. Use `xc-orchestration-viewer` for user-facing open, monitor, or visualize requests.

## References

- `assets/minimal-template.xml`: managed starter template.
- `assets/xc-orchestration-runtime.toml`: configuration template.
- `references/runtime-protocol.md`: public runtime protocol.
- `references/subagent-contract.md`: single-node worker contract.
- `references/subtree-embedding.md`: embedded template protocol.
