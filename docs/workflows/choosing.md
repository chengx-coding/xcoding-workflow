[简体中文](../zh-CN/workflows/choosing.md)

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

## Selection Rules

Use setup before other lifecycles when the required workshop bridge does not exist. Setup asks for project facts rather than inventing commands, conventions, or knowledge sources.

Use new-feature only when the product needs a new managed feature identity. If the behavior already exists and the goal is to place it under managed baselines, use adoption. If the feature is already managed, use ordinary work and supply its existing feature ID.

Use ordinary work for persistent work that may relate to zero, one, or several existing features. Select the mode from the requested outcome, then let evidence determine which optional documents and nodes are needed. A repair with a known cause need not repeat unnecessary diagnosis; an uncertain cause uses the [diagnosis contract](../../skills/xc-diagnosis/SKILL.md) before repair.

Use workflow evolution when the thing being changed is XC itself or a project's managed bridge. Its `scope` distinguishes `portable-core`, `project-bridge`, `agent-export`, `orchestration-template`, and `health-check` work so generic and project-specific concerns do not become mixed.

## Services Are Not Lifecycle Choices

[`xc-open-work-order`](../../skills/xc-open-work-order/SKILL.md) creates a durable workbench for a caller, but it is not a substitute for choosing a lifecycle. Analysis, clarification, implementation, verification, review, document evolution, and orchestration Skills are also bounded capabilities used by the selected lifecycle.
