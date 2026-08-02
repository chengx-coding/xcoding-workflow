---
name: "xc-workflow-evolution"
description: "Evolves portable XC workflow assets or a project's managed workflow bridge through the standard work-order and review model. Invoke when workflow contracts, templates, agents, exports, or bridge guidance need deliberate change."
---

# XC Workflow Evolution

`xc-workflow-evolution` applies the same durable workflow discipline to workflow maintenance. It distinguishes portable core changes from project-specific bridge changes before any implementation begins.

## Parameters

- `scope` - `enum`; required
  - Allowed values: `portable-core`, `project-bridge`, `agent-export`, `orchestration-template`, `health-check`.

- `workshop_path` - `path`; required
  - Scope: The target project's `.xcoding` workshop.

- `project_root` - `path`; required
  - Scope: The target project root forwarded to the managed `xc-work` operation.

- `request` - `string`; required
  - Scope: Requested workflow change, observed gap, or maintenance objective.

## Operation

Read the project bridge and use `scope`, `request`, and observable project context to confirm the six public `xc-work` facts. Invoke `xc-work` through its public Skill boundary with `operation=classify`, the original `request`, and `needs_persistence`, `material_impact`, `difficult_rollback`, `crosses_sessions`, `multiple_actors`, and `audit_required`. Apply the evidence, unknown, project-tightening, and unavailable-classification rules owned by `xc-work`; do not infer a direct route from task size or model capability.

When classification returns `managed` or becomes unavailable, invoke public `xc-work operation=run` with `workshop_path`, `project_root`, the original `request`, an empty `feature_ids` list, and the applicable `change` or `maintenance` mode. Record goal, analysis, selected solution, implementation evidence, and result through the normal work order documents. Omitting `operation` remains an equivalent managed entry for existing callers, but this routing operation uses the explicit public value.

An explicit caller may choose `xc-work operation=adaptive-run` for narrow workflow maintenance after running the public planner. Broad portable-core architecture, orchestration-template, or agent-export changes still require durable analysis, alternatives, independent review, and a user gate; a `fast` pace cannot remove those capabilities. Default workflow evolution continues to use the full `run` lifecycle for compatibility.

When classification returns `direct`, do not create a work order. Perform only the response-local, non-material action established by the all-`no` vector. If new evidence changes or invalidates any fact, stop before the next substantive action and re-enter through public `xc-work`; a managed or unavailable result proceeds through `operation=run`.

`xc-workflow-evolution` depends only on the documented `xc-work` Skill name and public parameters. It must not import, locate, or invoke another Skill's private scripts or references.

For portable-core changes, keep generic assets English, tool-neutral, and free of project paths, commands, frameworks, or business rules. For project-bridge changes, modify only the managed workshop bridge document through document evolution. For agent changes, update canonical sources, run the exporter, and run exporter check. For orchestration templates, edit the flow specification, rebuild the generated template through `xc-orchestration-author`, and smoke-test the runtime entry path.

## Controlled Skill Installation

Use `scripts/install_xc_skills.py` when a consumer project needs an explicit
copy of the current canonical `xc-*` Skill packages. The installer is
tool-neutral and requires explicit roots and a manifest path:

```powershell
python "$SKILL_DIR/scripts/install_xc_skills.py" `
  --source-root <canonical_source_root> `
  --target-root <consumer_asset_root> `
  --manifest <consumer_manifest_path>

python "$SKILL_DIR/scripts/install_xc_skills.py" `
  --source-root <canonical_source_root> `
  --target-root <consumer_asset_root> `
  --manifest <consumer_manifest_path> `
  --check
```

The installer copies complete `xc-*` packages, records source revision and
file hashes, refuses unmanaged target drift, and never manages non-`xc-*`
packages. `--check` is read-only. Consumer-specific paths, installation
policy, and deletion gates belong in the consumer bridge or managed work order, not
in this Skill.

## Constraints

- Do not hand-edit generated agent outputs or generated orchestration templates.
- Do not alter managed runtime trees outside the runtime public interface.
- A broad architecture change requires analysis, documented alternatives, review, and an explicit user gate before implementation.
