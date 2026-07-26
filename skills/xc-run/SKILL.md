---
name: "xc-run"
description: "Creates standard workflow run directories inside a project's .xcoding context. Invoke when a workflow needs a durable run ID, runtime directory, or artifact directory."
---

# XC Run

`xc-run` creates a standard durable run directory. It validates that the supplied `.xcoding` directory belongs to an independent context Git worktree, generates a collision-safe timestamp-and-slug run ID, creates the standard directories, and returns their absolute paths as JSON.

## Parameters

### Public Parameters

- `context_dir` - `path`; required
  - Scope: The project `.xcoding` directory that contains `runs/`.
  - Side effects: The script creates `runs/` and the selected run directory.
  - Propagation: No downstream propagation.

- `project_root` - `path`; optional, defaults to the current working directory
  - Scope: The business project root used to verify that context Git history is independent from the business code repository.
  - Side effects: Validation only.
  - Propagation: No downstream propagation.

- `topic` - `string`; optional, inferred from the request when omitted
  - Scope: Human-readable slug portion of the generated run ID.
  - Side effects: Affects the directory name only.
  - Propagation: No downstream propagation.

- `run_id` - `string`; optional
  - Scope: Explicit run identifier. When omitted, the script creates `YYYYMMDD-HHMM-<topic>`.
  - Side effects: Affects the directory name only.
  - Propagation: No downstream propagation.

- `feature_ids` - `string[]`; optional
  - Scope: Feature identifiers associated with the run. A run may have zero, one, or multiple feature identifiers.
  - Side effects: Returned as metadata only; the script does not create feature directories.
  - Propagation: Returned to the calling workflow for tree and document initialization.

## Operation

Run:

```powershell
python "$SKILL_DIR/scripts/create_run.py" `
  --context-dir <context_dir> `
  --project-root <project_root> `
  --topic <topic> `
  --feature-id <feature_id>
```

The script creates:

```text
<context_dir>/runs/<run_id>/
  artifacts/
  runtime/
```

Use the returned `runtime_dir` to initialize the main orchestration tree. `xc-run` does not create documents, trees, logs, feature directories, or Git commits.

## Constraints

- The resolved `context_dir` MUST be inside a Git worktree dedicated to workflow context.
- The script MUST NOT create a feature directory. Only the new-feature and feature-adoption workflows may do so.
- Callers MUST use the returned paths rather than reconstructing run paths.
- The script handles slug normalization and collision suffixes internally.
