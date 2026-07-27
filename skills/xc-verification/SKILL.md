---
name: "xc-verification"
description: "Executes and records project-defined verification for a workflow node or run. Invoke when implementation, diagnosis, adoption, or a feature baseline requires test and validation evidence."
---

# XC Verification

`xc-verification` executes validation defined by `.xcoding/WORKFLOW.md`, a feature `verification.md`, or a caller-supplied accepted solution. It records command outcomes and coverage gaps in a node artifact; run-level conclusions belong in `result.md`.

## Parameters

- `run_dir` - `path`; required
  - Scope: Existing run directory that owns verification artifacts and, when applicable, `result.md`.

- `verification_scope` - `enum`; required
  - Allowed values: `focused`, `feature`, `regression`, `adoption`, `diagnosis-verify`, `workflow`.

- `inputs` - `path[]`; optional
  - Scope: Feature verification contracts, run solution, diagnosis artifacts, changed-path summaries, and user constraints.

- `artifact_path` - `path`; required
  - Scope: A `node-artifact` location for the execution summary and evidence.

## Operation

Read the project bridge before choosing commands. Select the smallest command set that proves the requested acceptance conditions, then broaden it when shared contracts or cross-module behavior changed. Record each command, pass/fail/blocked outcome, relevant assertion coverage, environment prerequisites, and unexecuted checks with reasons.

When a feature verification baseline exists, map evidence to its requirement IDs. A passing command does not establish an untested requirement; record such gaps explicitly. Failed verification is a workflow result, not an opportunity to silently change acceptance criteria.

## Constraints

- Do not invent test commands, tools, environments, thresholds, or pass criteria.
- Do not modify product behavior only to make a validation command pass without returning to the caller's solution and implementation nodes.
- Preserve credentials, sensitive output, and raw logs outside general node artifacts unless the project bridge explicitly requires durable retention.
