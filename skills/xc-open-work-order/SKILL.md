---
name: "xc-open-work-order"
description: "Opens a managed work order and creates its standard workbench inside a project's .xcoding workshop. Invoke when a workflow needs a durable work order ID, runtime path, or artifacts path."
---

# XC Open Work Order

`xc-open-work-order` opens one durable work order. It validates that the supplied `.xcoding` workshop belongs to an independent Git worktree, generates a collision-safe timestamp-and-slug work order ID, creates the standard workbench directories, and returns their absolute paths as JSON.

## Parameters

### Public Parameters

- `workshop_path` - `path`; required
  - Scope: The project `.xcoding` workshop that contains `work-orders/`.
  - Side effects: The script creates `work-orders/` and the selected workbench.
  - Propagation: No downstream propagation.

- `project_root` - `path`; optional, defaults to the current working directory
  - Scope: The business project root used to verify that workshop Git history is independent from the business code repository.
  - Side effects: Validation only.
  - Propagation: No downstream propagation.

- `topic` - `string`; optional, inferred from the request when omitted
  - Scope: Human-readable slug portion of the generated work order ID.
  - Side effects: Affects the directory name only.
  - Propagation: No downstream propagation.

- `work_order_id` - `string`; optional
  - Scope: Explicit work order identifier. When omitted, the script creates `YYYYMMDD-HHMM-<topic>`.
  - Side effects: Affects the directory name only.
  - Propagation: No downstream propagation.

- `feature_ids` - `string[]`; optional
  - Scope: Feature identifiers associated with the work order. A work order may have zero, one, or multiple feature identifiers.
  - Side effects: Returned as metadata only; the script does not create feature directories.
  - Propagation: Returned to the calling workflow for tree and document initialization.

## Operation

Run:

```powershell
python "$SKILL_DIR/scripts/open_work_order.py" `
  --workshop <workshop_path> `
  --project-root <project_root> `
  --topic <topic> `
  --work-order-id <work_order_id> `
  --feature-id <feature_id>
```

The script creates:

```text
<workshop_path>/work-orders/<work_order_id>/
  artifacts/
  runtime/
```

Use the returned `runtime_path` to initialize the main orchestration tree. `xc-open-work-order` does not create documents, trees, logs, feature directories, or Git commits.

## Constraints

- The resolved `workshop_path` MUST be the fixed `.xcoding` path inside a dedicated workshop Git worktree.
- The script MUST NOT create a feature directory. Only the new-feature and feature-adoption workflows may do so.
- Callers MUST use the returned paths rather than reconstructing workbench paths.
- The script handles slug normalization and collision suffixes internally.
