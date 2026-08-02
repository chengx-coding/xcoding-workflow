**Language:** **English** | [简体中文](../zh-CN/workflows/choosing.md)

# Choosing A Workflow

Choose the lifecycle from the state of the project and the intended outcome. Do not choose a feature lifecycle merely because work is large, and do not use ordinary work to create a feature implicitly.

## Decision Table

| Situation | Entry point | Result |
| --- | --- | --- |
| The project is adopting XC, or required workshop bridge documents are missing | [`xc-workshop-setup`](../../skills/xc-workshop-setup/SKILL.md) | Creates the managed project workflow and knowledge guidance through a setup work order; it does not create a business feature |
| The requested behavior needs a new, explicitly managed feature identity | [`xc-new-feature`](../../skills/xc-new-feature/SKILL.md) | Creates the feature directory, approves feature baselines, then implements and verifies the feature |
| Existing behavior is not managed yet but needs durable baselines for future evolution | [`xc-feature-adoption`](../../skills/xc-feature-adoption/SKILL.md) | Derives and approves baselines from current code and test evidence without changing product behavior |
| Facts or impact must be established, but no product change is requested | [`xc-work`](../../skills/xc-work/SKILL.md) with `mode=investigation` | Produces evidence and a result; solution, implementation, and verification can be omitted |
| Existing code, configuration, or behavior must change | `xc-work` with `mode=change` | Selects the needed analysis, solution, implementation, and verification stages |
| A reported failure needs repair | `xc-work` with `mode=repair` | Uses diagnosis when the root cause is uncertain, then returns to the approved change path |
| Documents, code, or evidence need read-only assessment | `xc-work` with `mode=review` | Produces analysis and review artifacts without modifying the reviewed inputs |
| Routine upkeep is needed without creating a feature | `xc-work` with `mode=maintenance` | Runs only the documents and execution nodes required for the maintenance outcome |
| Portable workflow contracts, project bridge guidance, agents, exports, or orchestration templates must change | [`xc-workflow-evolution`](../../skills/xc-workflow-evolution/SKILL.md) | Applies the standard work-order and review discipline to workflow maintenance |

## Direct Or Managed Governance

Before substantive action, confirm the following six facts from host and security rules, the user's explicit request, the applicable project bridge, public Skill contracts, and observable task facts. Each value is exactly `no`, `yes`, or `unknown`.

| Fact | Use `yes` when | Use `no` only when |
| --- | --- | --- |
| `needs_persistence` | Correct completion writes or retains project or external state, durable documents, recoverable progress, or evidence usable after the current response | No durable state is written and the result is consumed in the current interaction |
| `material_impact` | Work changes shared code, a public contract, user data, permissions, production or infrastructure state, a security boundary, or a release asset | Work is read-only or an isolated temporary transformation with none of those effects |
| `difficult_rollback` | No confirmed, verified, lossless one-step recovery exists, or an irreversible external side effect exists | Work is read-only or has a confirmed deterministic one-step full recovery |
| `crosses_sessions` | Completion requires a later session, restart, scheduled wait, asynchronous external result, or cross-run recovery | All inputs are available for one continuous execution with no wait or resume requirement |
| `multiple_actors` | At least two independent people, agents, approvers, or external systems own coordinated decisions or deliverables | One actor owns the work with no approval, handoff, or parallel dependency |
| `audit_required` | The user, law, project bridge, Skill, or workflow contract requires retained traceability, approval, verification, review, or a commit | Applicable policy has been read and confirmed to require none of these |

Use `unknown` whenever the evidence does not justify `yes` or `no`, including an unresolved conflict. Only the all-`no` vector permits direct work. Any `yes` or `unknown` selects managed work, and an explicit managed selection is never downgraded automatically.

The applicable project bridge is read before the vector is confirmed. It may tighten `no` to `unknown` or `yes`, and `unknown` to `yes`; it cannot relax `yes` or `unknown` to `no`, or `yes` to `unknown`. When project context is expected but the bridge or an applicable rule is unavailable, at least `audit_required` is `unknown`.

## Classification Boundary

Use the executable public [`xc-work operation=classify`](../../skills/xc-work/SKILL.md) boundary:

```console
python skills/xc-work/scripts/classify.py [--needs-persistence no|yes|unknown] [--material-impact no|yes|unknown] [--difficult-rollback no|yes|unknown] [--crosses-sessions no|yes|unknown] [--multiple-actors no|yes|unknown] [--audit-required no|yes|unknown]
```

The adapter accepts every fact as optional, fills omissions with `unknown`, invokes and validates the strict low-level classifier, and always exits successfully. Malformed, duplicate, or contradictory input; a missing executable; timeout or nonzero exit; malformed JSON; and an unknown schema or route all produce `route=managed`, `classification_status=escalated`, and reason `classification-unavailable`. The low-level classifier still requires all six facts exactly once and retains nonzero diagnostic errors; it is not the public lifecycle command.

The adapter validates only facts and observable subprocess output. It does not authenticate the caller, Python interpreter, executable bytes, or host and provides no host mediation or attestation. Classification itself creates no workshop, work order, document, runtime tree, artifact, or commit.

Examples:

- Correcting one spelling in temporary text, without writing a file or retaining evidence, can remain direct when all six facts are confirmed `no`.
- Explaining a supplied code fragment can remain direct under the same all-`no` rule; explicitly choosing `operation=run` still starts managed work.
- A direct investigation that discovers a need for cross-session tracking must stop before the next substantive action, carry forward the original request, completed actions, and evidence, and enter `xc-work operation=run`.
- A short credential rotation or destructive command is managed immediately when material impact or rollback is `yes` or `unknown`; request length does not reduce governance.

A stronger model may keep more direct-path reasoning in one main session and may reduce unnecessary delegation after the route is selected. It cannot change confirmed facts, bypass managed controls, weaken artifacts or verification, or replace a scoped control packet with full-tree access. Governance has no model-specific profiles.

## Proportional Managed Effort

Governance and managed effort are separate decisions. Omitted `operation` and `operation=run` retain the full lifecycle. An explicit `operation=adaptive-run` opens a managed work order from a minimal root and sequence dynamic group, then adds only plan-required capabilities.

The read-only `operation=plan` uses the six governance facts plus bridge policy, scope, clarity, risk, verification, coordination, duration, audit, and `adaptive|fast|thorough` pace. Capabilities merge monotonically: tighter evidence or policy can add work but cannot remove required work. `fast` uses the required minimum; `thorough` may add analysis, review, recovery exercise, and regression depth.

A minimal mutation can use one combined implementation/focused-verification leaf and one plan-specific finalizer, with no mandatory `goal.md`, `analysis.md`, `solution.md`, or `result.md`. Module, uncertain, high-risk, collaborative, cross-session, or full-audit facts progressively add separate verification, durable documents, gates, review, and recovery. Adaptive work has no generic global node ceiling; individual loops remain bounded.

Workflow measurements named `context_bytes` count normalized UTF-8 runtime protocol payload bytes. They are not token counts, model latency, execution latency, cost, or quality measurements.

## Selection Rules

Use setup before other lifecycles when the required workshop bridge does not exist. Setup asks for project facts rather than inventing commands, conventions, or knowledge sources.

Use new-feature only when the product needs a new managed feature identity. If the behavior already exists and the goal is to place it under managed baselines, use adoption. If the feature is already managed, use ordinary work and supply its existing feature ID.

Use ordinary work for persistent work that may relate to zero, one, or several existing features. Select the mode from the requested outcome, then let evidence determine which optional documents and nodes are needed. A repair with a known cause need not repeat unnecessary diagnosis; an uncertain cause uses the [diagnosis contract](../../skills/xc-diagnosis/SKILL.md) before repair.

Use workflow evolution when the thing being changed is XC itself or a project's managed bridge. Its `scope` distinguishes `portable-core`, `project-bridge`, `agent-export`, `orchestration-template`, and `health-check` work so generic and project-specific concerns do not become mixed.

## Services Are Not Lifecycle Choices

[`xc-open-work-order`](../../skills/xc-open-work-order/SKILL.md) creates a durable workbench for a caller, but it is not a substitute for choosing a lifecycle. Analysis, clarification, implementation, verification, review, document evolution, and orchestration Skills are also bounded capabilities used by the selected lifecycle.
