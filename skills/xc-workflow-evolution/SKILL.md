---
name: "xc-workflow-evolution"
description: "Evolves portable XC workflow assets or a project's managed workflow bridge through the standard run and review model. Invoke when workflow contracts, templates, agents, exports, or bridge guidance need deliberate change."
---

# XC Workflow Evolution

`xc-workflow-evolution` applies the same durable workflow discipline to workflow maintenance. It distinguishes portable core changes from project-specific bridge changes before any implementation begins.

## Parameters

- `scope` - `enum`; required
  - Allowed values: `portable-core`, `project-bridge`, `agent-export`, `orchestration-template`, `health-check`.

- `context_dir` - `path`; required
  - Scope: The target project's `.xcoding` context directory.

- `request` - `string`; required
  - Scope: Requested workflow change, observed gap, or maintenance objective.

## Operation

Create or reuse a zero-feature ordinary run unless the task is demonstrably trivial and needs no durable state. Record goal, analysis, selected solution, implementation evidence, and result through the normal run documents.

For portable-core changes, keep generic assets English, tool-neutral, and free of project paths, commands, frameworks, or business rules. For project-bridge changes, modify only the managed context document through document evolution. For agent changes, update canonical sources, run the exporter, and run exporter check. For orchestration templates, edit the flow specification, rebuild the generated template through `xc-orchestration-author`, and smoke-test the runtime entry path.

## Constraints

- Do not hand-edit generated agent outputs or generated orchestration templates.
- Do not alter managed runtime trees outside the runtime public interface.
- A broad architecture change requires analysis, documented alternatives, review, and an explicit user gate before implementation.
