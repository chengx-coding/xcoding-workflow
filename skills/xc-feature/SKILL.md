---
name: "xc-feature"
description: "Creates and validates explicit managed feature directories inside a project's .xcoding workshop. Invoke only from new-feature or feature-adoption workflows."
---

# XC Feature

`xc-feature` owns the durable feature-directory boundary. It creates `.xcoding/features/<feature-id>/` only after a new-feature or feature-adoption workflow explicitly selects the identifier. It never creates a feature from an ordinary work order and never creates baseline documents itself.

## Parameters

- `workshop_path` - `path`; required
  - Scope: The fixed `.xcoding` workshop in an independent workshop Git worktree.
  - Side effects: The `init` operation creates one empty feature directory.

- `feature_id` - `string`; required
  - Scope: A stable feature identifier. The default lifecycle convention is a lowercase slug; a project bridge may define another safe identifier convention.
  - Side effects: Determines the feature-directory name.

## Operation

```powershell
python "$SKILL_DIR/scripts/manage_feature.py" init `
  --workshop <workshop_path> `
  --feature-id <feature_id>
```

The script validates the fixed workshop location, rejects path traversal and existing feature directories, creates the directory, and returns its authoritative absolute path as JSON. The caller creates `contract.md`, `solution.md`, and `verification.md` through document-evolution subtrees after this operation.

## Constraints

- Only `xc-new-feature` and `xc-feature-adoption` may call `init`.
- An ordinary work order may reference existing feature IDs but MUST NOT create or adopt a feature implicitly.
- The feature directory and its baseline documents are workshop-Git artifacts and must be declared by the terminal node that creates or changes them.
- The caller uses the project bridge to determine the identifier convention; this generic capability only enforces a safe portable path segment.
