# Investigation and Decisions

**Language:** **English** | [简体中文](../../zh-CN/reference/skills/investigation-and-decisions.md)

These supporting Skills gather evidence or resolve decisions before implementation.

## `xc-conventions`

[Canonical contract](../../../skills/xc-conventions/SKILL.md)

- **Invoke when:** a substantive change is about to happen, to discover the project's own development conventions that live outside the bridge.
- **Purpose:** proportional convention discovery across three tiers: an L0 direct-path tripwire, the mandatory L1 preparation scan, and L2 deep study.
- **Public entry:** required `project_root` and `tier` (`l0-tripwire`, `l1-scan`, `l2-study`); optional `targets`, `bridge_locations`, and `workbench_path`.
- **Typical usage:** the deterministic scanner enumerates and classifies candidates (declared C1 instruction files, configured C2 formatter/linter/CI signals); the agent reads the applicable C1 rules and routes a compact discovery record into implementation and verification inputs.
- **Boundaries:** L1 is a floor independent of the skippable analysis stage; a check always leaves a record (`found` or `not-applicable`) and a scan failure fails closed; undeclared de-facto patterns stay weak, labeled inference; the Skill does not connect to a knowledge base or parse rule semantics.

## `xc-analysis`

[Canonical contract](../../../skills/xc-analysis/SKILL.md)

- **Invoke when:** a managed work order needs facts, impact analysis, reconciliation, diagnosis support, option comparison, or review support.
- **Purpose:** produce evidence artifacts and synthesize accepted facts, hypotheses, risks, alternatives, and unknowns into work-order analysis.
- **Public entry:** required `workbench_path` and `analysis_scope` (`investigation`, `reconciliation`, `diagnosis-support`, `solution-support`, `review-support`, or `convention-review`); optional `feature_ids` and `inputs`.
- **Typical usage:** schedule independent evidence perspectives, then synthesize them through a document-evolution subtree.
- **Boundaries:** analysis changes neither product code nor feature baselines; unsupported claims and conflicting evidence must not be silently merged.

## `xc-clarify`

[Canonical contract](../../../skills/xc-clarify/SKILL.md)

- **Invoke when:** evidence leaves material human-owned decisions unresolved, or the user asks to clarify or challenge a request or plan.
- **Purpose:** run a bounded, traceable sequence of one-decision-at-a-time gates in `discover` or `challenge` mode.
- **Public entry:** required `workbench_path`, `mode`, `subject`, and `instance_id`; optional `inputs` and `initial_decision_budget`.
- **Typical usage:** embed the clarification template in an existing lifecycle, gather evidence first, record full answers in one session artifact, and hand decisions back to analysis and solution selection.
- **Boundaries:** it is not a standalone work order and does not replace evidence gathering, review, solution approval, or verification; long content never belongs in the blackboard.

## `xc-diagnosis`

[Canonical contract](../../../skills/xc-diagnosis/SKILL.md)

- **Invoke when:** a reported failure's root cause, failure mode, or repair direction is uncertain.
- **Purpose:** reproduce the problem, collect bounded evidence, and record confirmed or suspected causes and a repair direction without applying the repair.
- **Public entry:** required `workbench_path` and `problem_statement`; optional `mode` (`diagnose` or `verify`) and `inputs`.
- **Typical usage:** reproduce with project-defined commands, inspect code and runtime evidence, then return sufficient findings to the ordinary repair lifecycle.
- **Boundaries:** suspected causes remain labeled; unsafe external access or destructive reproduction blocks the work, and temporary instrumentation requires authorization and removal.
