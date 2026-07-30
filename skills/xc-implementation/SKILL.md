---
name: "xc-implementation"
description: "Executes one approved implementation node in a managed work order. Invoke after a work order solution and required gates establish the requested code or configuration change."
---

# XC Implementation

`xc-implementation` defines the worker contract for one approved implementation node. The caller's runtime tree owns decomposition, dependencies, retries, review loops, verification, and completion. This Skill does not create an implicit task ledger.

## Parameters

- `workbench_path` - `path`; required
  - Scope: Existing workbench that supplies the work order goal, accepted solution, artifacts, and runtime node contract.

- `work_scope` - `string`; required
  - Scope: The node's bounded code, configuration, migration, or documentation change.

- `inputs` - `path[]`; required
  - Scope: Approved work order solution, relevant feature baselines, analysis artifacts, and project bridge references.

- `artifact_path` - `path`; required
  - Scope: Node artifact recording changed paths, validation, and residual risk.

## Operation

Read the supplied node contract and approved inputs, make the smallest coherent change, and preserve unrelated worktree changes. Run focused verification before reporting success. Record changed paths, validation commands and outcomes, baseline impact, and any unresolved issue in the declared artifact. Implementation artifacts default to internal English; localize only an explicitly declared `metadata.artifact.audience=user` report using its resolved artifact language.

When implementation evidence changes a feature baseline, add a separate document-evolution subtree or user gate through the caller's runtime workflow. Do not overwrite a baseline opportunistically from an implementation node.

## Constraints

- Execute exactly one runtime node and report only through the runtime public command.
- Do not introduce unapproved product scope, migrations, or external side effects.
- A failed or blocked implementation preserves evidence and lets the caller choose retry, alternate work, or a user gate.
