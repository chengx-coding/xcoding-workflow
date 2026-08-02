---
name: "xc-verification"
description: "Executes and records project-defined verification for a workflow node or work order. Invoke when implementation, diagnosis, adoption, or a feature baseline requires test and validation evidence."
---

# XC Verification

`xc-verification` executes validation defined by `.xcoding/WORKFLOW.md`, a feature `verification.md`, or a caller-supplied accepted solution. It records command outcomes and coverage gaps in a node artifact; work-order-level conclusions belong in `result.md`.

## Parameters

- `workbench_path` - `path`; required
  - Scope: Existing workbench that owns verification artifacts and, when applicable, `result.md`.

- `verification_scope` - `enum`; required
  - Allowed values: `focused`, `feature`, `regression`, `adoption`, `diagnosis-verify`, `workflow`.

- `inputs` - `path[]`; optional
  - Scope: Feature verification contracts, work order solution, diagnosis artifacts, changed-path summaries, and user constraints.

- `artifact_path` - `path`; required
  - Scope: A `node-artifact` location for the execution summary and evidence.

## Operation

Read the project bridge before choosing commands. Select the smallest command set that proves the requested acceptance conditions, then broaden it when shared contracts or cross-module behavior changed. Record each command, pass/fail/blocked outcome, relevant assertion coverage, environment prerequisites, and unexecuted checks with reasons.

When a feature verification baseline exists, map evidence to its requirement IDs. A passing command does not establish an untested requirement; record such gaps explicitly. Failed verification is a workflow result, not an opportunity to silently change acceptance criteria.

Verification artifacts default to internal English. A user-facing verification report must be explicitly marked with `metadata.artifact.audience=user` and uses the resolved `metadata.artifact.content_language`. It follows the public `xc-document` human-readable authoring default and supplied explicit authoring requirements, while preserving commands and raw output exactly.

## Dynamic Node Contract

Before `add-node`, the caller writes the actual terminal implementation or diagnosis source IDs as a compact JSON array to a node-specific blackboard key such as `verification.sources.<logical-key>`. The dynamic task declares all of:

```text
metadata.control_packet.category.implementation-records.selectors=["bb:verification.sources.<logical-key>"]
metadata.control_packet.category.implementation-records.min_sources=1
metadata.control_packet.category.implementation-records.artifact_min=1
metadata.completion.required_fields=["summary","validation"]
metadata.completion.artifacts.min=1
metadata.completion.artifacts.max=1
metadata.completion.artifacts.path=literal:<artifact_path>
```

Select only terminal leaves whose artifacts supply the evidence this verification scope needs. Increase thresholds for scopes that require multiple independent records; do not use a group, ancestor, guessed ID, or unrelated sibling as a source. Read `control-packet` before `start`, run the project-defined checks, and complete with non-empty summary and validation plus exactly `artifact_path`.

## Constraints

- Do not invent test commands, tools, environments, thresholds, or pass criteria.
- Do not modify product behavior only to make a validation command pass without returning to the caller's solution and implementation nodes.
- Preserve credentials, sensitive output, and raw logs outside general node artifacts unless the project bridge explicitly requires durable retention.
