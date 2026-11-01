---
name: "xc-workflow-evolution"
description: "Evolves portable XC workflow assets or a project's managed workflow bridge through the standard work-order and review model. Invoke when workflow contracts, templates, agents, exports, or bridge guidance need deliberate change."
---

# XC Workflow Evolution

Applies the durable workflow discipline to workflow maintenance. Separate portable-core changes from
project-specific bridge changes before implementation.

## Parameters

- `scope` — `enum`; required: `portable-core`, `project-bridge`, `agent-export`,
  `orchestration-template`, `health-check`.
- `workshop_path` — `path`; required: the target project's `.xcoding` workshop.
- `project_root` — `path`; required: the target project root.
- `request` — `string`; required: requested change, observed gap, or maintenance objective.

## Operation

Read the project bridge and confirm the six public `xc-work` facts through public
`xc-work operation=classify`: `needs_persistence`, `material_impact`, `difficult_rollback`,
`crosses_sessions`, `multiple_actors`, `audit_required`. Apply `xc-work`'s evidence/unknown/project-
tightening rules; do not infer a direct route from task size.

When classification returns `managed` or is unavailable, invoke public `xc-work operation=run` with the
workshop, project root, original request, empty feature list and `change`/`maintenance` mode. An
explicit caller may use `adaptive-run` for narrow maintenance; broad portable-core, template or
agent-export changes still require analysis, alternatives, review and a user gate. `direct` is only for
a response-local, non-material all-`no` vector; re-enter public `xc-work` if a fact changes.

For portable-core changes, keep assets English, tool-neutral and free of project facts. For bridge
changes, modify only the managed bridge. For agent changes, edit canonical sources, export and check.
For templates, edit the flow spec, rebuild via `xc-orchestration-author`, and smoke-test the entry path.

## Controlled installation

`scripts/install_xc_skills.py` copies complete canonical `xc-*` packages with source revision and
hashes, refuses unmanaged target drift, and never manages non-`xc-*` packages. `--check` is read-only.
Consumer paths, installation policy and deletion gates belong in the bridge or work order, not here.

```powershell
python "$SKILL_DIR/scripts/install_xc_skills.py" --source-root <source> --target-root <target> --manifest <manifest>
python "$SKILL_DIR/scripts/install_xc_skills.py" --source-root <source> --target-root <target> --manifest <manifest> --check
```

## Self-evolution method

For a self-evolution line, read
[`references/self-evolution-discipline.md`](references/self-evolution-discipline.md) and
[`references/generality-and-applicability.md`](references/generality-and-applicability.md). The
discipline owns the method (startup, divergence/convergence, meta-review, architecture health, line
closure and delegated gates); this Skill owns routing, placement, status and force.

- **One owner per rule.** Stable contract/invariants here; method/checklists/records in references;
  stage actions in node instructions. Do not duplicate; update links/tests atomically when moving.
- **Startup.** Reconstruct prior round notes, the project's architecture debt/decisions, the current
  hypothesis and what would refute it.
- **Status.** `proposed` → `validated-in-class` → `promoted-universal`; also `demoted`/`retired`.
  A task-class rule starts `proposed`; a second independent instance is needed for `validated-in-class`;
  a different-class probe plus a negative/not-applicable probe is needed for universal promotion.
- **Line closure.** End with `continue`, `promote`, `refactor` or `stop`; a line closure requires a
  recorded minimal meta-review (what changed, what was learned, keep/demote/retire, architecture
  signal, decision, next trigger). "Defer to line end" is not a decision.
- **Force.** Convention-only unless an existing mechanical check says otherwise; no new runtime
  command, state, node type or configuration surface.

This discipline applies to self-evolution lines only; ordinary work orders and user gates are
unchanged.

## Architecture-preserving evolution

Prefer the smallest correct fix that reuses an existing mechanism over a new command/state/config/node/
cross-cutting check. Evaluate the whole architecture, not the local symptom; record whether the change
leaves the system more coherent or more tangled. If the correct fix is a refactor, propose it rather
than layering a patch; behavior/contract-changing refactors still require analysis, alternatives,
review and a user gate. Record deferred work and accepted trade-offs as durable notes.

## Core design alignment

Before selecting or implementing a change, re-check the project's declared authoritative core design
(the bridge names its location). Judge the iteration against its principles, invariants and decision
criteria. Any change to that design requires the user's prior confirmation before it takes effect; propose it, do not edit it
as a side effect. This is documentation discipline plus a phrase-level test, not mechanical proof of
reading or confirmation. Keep project-specific locations/numbering in the bridge.

## Project version policy

Apply public `xc-work` Project Version Decisions on full and adaptive evolution. Read numbering/release
rules from the bridge, assess impact before closure, and retain the recommendation and exact
consent/deferral. A workflow improvement does not authorize a version bump, release or tag. Keep
project-specific numbering out of portable assets.

## Constraints

- Do not hand-edit generated agent outputs or templates.
- Do not alter managed runtime trees outside the runtime public interface.
- A broad architecture change requires analysis, alternatives, review and a user gate.
- Do not add a disproportionate mechanism; record whole-architecture impact and deferred trade-offs.
- Do not change the authoritative core design without prior user confirmation.
