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

## Self-Evolution Discipline

When the requested change is part of a **self-evolution/optimization line** rather than a one-off
maintenance edit, read and apply [`references/self-evolution-discipline.md`](references/self-evolution-discipline.md)
before starting or continuing the line. It owns the detailed method; this section is the contract.

- **Meta-cognitive checkpoint.** After 3 completed iterations in a line, or at the project's version
  boundary, or on a direction/patch/architecture/regression/generality/metric-change/user-report
  signal, pause for an independent meta-review. The review has a 45–60 minute time-box, records a
  decision (`continue|simplify|refactor|change-metric|pause|stop|defer`) and may pause the line, but
  cannot make material changes unilaterally. It does not review itself recursively.
- **Content placement.** Stable contract and invariants stay in `SKILL.md`; detailed method,
  checklists and record formats stay in references; stage-specific actions and attention stay in
  orchestration node instructions. Keep one owner per rule, do not duplicate, and record an
  equivalence check when moving content.
- **Divergence and convergence.** Context divergence (bridge, instructions, conventions, prior
  decisions, tests/CI, ownership, history) is mandatory even for specific tasks. Solution divergence
  is adaptive; self-evolution must consider do-nothing, minimal fix, simplify, refactor and
  change-metric/process. Converge with evidence, rejected options, uncertainty and a stopping reason;
  option count is not a metric.
- **Delegated gates.** Only an explicit user grant for an autonomous multi-round self-evolution line
  can delegate an otherwise user-owned gate. A delegated gate is **run**, not skipped, and is recorded
  with its grant, scope, alternatives, materiality, evidence, risk, rollback and independent review.
  `result.md` must contain a dedicated autonomous-decisions section. Expanding the grant, security/
  permissions/secrets/compliance, destructive history/artifact deletion, release/tag/publication,
  core values or explicit user constraints, host restrictions, and out-of-grant or irreversible
  decisions remain non-delegable.

This discipline applies to self-evolution lines only. Ordinary work orders and their user gates are
unchanged. It adds no runtime command, state, node type or configuration surface; use the existing
nodes, artifacts and gates. All new rules are convention-only unless an existing mechanical check says
otherwise.

## Applicability and Generality

Before adding or promoting a self-evolution rule, read
[`references/generality-and-applicability.md`](references/generality-and-applicability.md). It requires
every rule to declare its scope (`universal`, `task-class`, `project-specific`, `sample-specific`),
`applies_when`, `does_not_apply`, evidence surface, owner and promotion status.

- Universal rules must be surface-neutral and live in the generic Skill.
- Task-class rules live in the owning profile (for example visual, CLI/library/API or docs), never in
  the universal path. Visual rules apply only when the task has a visual output
  surface; a pure code/docs task must not produce screenshots or visual-state evidence.
- A rule from one sample/task is not universal. Promotion to `universal` requires a probe in a
  different task class plus a negative/not-applicable probe; wording alone is not generality.
- The independent review must apply the rule to a non-originating class and record an applicability
  map. A wording-only review cannot support universal promotion.
- The meta-review must ask whether the rule belongs in the universal core, a profile, the bridge or
  the sample, and must demote/retire overgeneralized rules.

## Architecture-Preserving Evolution

Prefer the smallest correct fix that reuses an existing mechanism or established pattern over a new command, new state, new configuration surface, new node type, or new cross-cutting check. A minor or low-value problem does not justify durable added complexity.

Evaluate every change against the whole architecture, not only its local symptom, and record in the work order whether the change leaves the system more coherent or more tangled. When a local repair would degrade the overall architecture, reconsider it. When the correct way to support a capability or fix a real defect is a local or broader refactor, identify and propose that refactor rather than layering a patch that preserves a worse structure; a behavior- or contract-changing refactor still requires analysis, documented alternatives, review, and an explicit user gate. Record deferred work and accepted trade-offs as durable structured project notes so a later evolution keeps the original reasoning.

## Core Design Alignment

Before selecting or implementing any workflow-asset change, re-check the project's declared authoritative core design document, which the project bridge names and is the only source of its location and identity. Read that document and judge this iteration's intended change against the principles, invariants, and decision criteria it states. A previous iteration's re-check does not exempt the current one.

Any adjustment, improvement, or change to that core design requires the user's prior confirmation before it takes effect. An implementer who concludes that the core design should change proposes the change and obtains that confirmation; it does not edit the design as a side effect of the work, and it does not bypass or reinterpret the design because a different course is more convenient.

**Documentation-only strength.** This clause adds no mechanical enforcement by itself: its entire force is documentation discipline plus one phrase-level test that the clause is still stated. Its constraint reduces to a duty to read the declared design before acting and a duty to propose a design change rather than assume it. Nothing verifies that an iteration actually read the design, and nothing verifies that a user actually confirmed a change. Keep project-specific locations, titles, and numbering rules out of portable assets; the project bridge supplies them.

## Project Version Policy

Apply the public Project Version Decisions contract of `xc-work` on full and adaptive evolution work. Read numbering and release choices from the project bridge, assess version impact before closure, and retain the recommendation and exact consent or deferral in the existing work-order artifacts. A workflow improvement does not itself authorize a version bump or publication. Keep project-specific numbering rules out of portable assets.

## Constraints

- Do not hand-edit generated agent outputs or generated orchestration templates.
- Do not alter managed runtime trees outside the runtime public interface.
- A broad architecture change requires analysis, documented alternatives, review, and an explicit user gate before implementation.
- Do not add a new mechanism disproportionate to the problem; prefer reusing an existing mechanism, and record the whole-architecture impact and any deferred trade-offs.
- Do not change the project's declared authoritative core design without the user's prior confirmation, and do not skip re-checking that design before the work of an iteration begins.
