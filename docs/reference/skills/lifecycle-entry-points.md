# Lifecycle Entry Points

**Language:** **English** | [简体中文](../../zh-CN/reference/skills/lifecycle-entry-points.md)

These Skills select and govern complete workflow lifecycles.

## `xc-workshop-setup`

[Canonical contract](../../../skills/xc-workshop-setup/SKILL.md)

- **Invoke when:** a project first adopts XC or required workshop documents are missing.
- **Purpose:** establish the managed `.xcoding/WORKFLOW.md` and `.xcoding/KNOWLEDGE.md` documents without creating a business feature.
- **Public entry:** required `workshop_path`; optional `project_root` and `auto_commit`.
- **Typical usage:** open a setup work order, evolve and validate both workshop documents, then finalize them as workshop artifacts.
- **Boundaries:** do not invent project facts; validate documents through the document service and access runtime state only through public runtime commands.

## `xc-open-work-order`

[Canonical contract](../../../skills/xc-open-work-order/SKILL.md)

- **Invoke when:** a lifecycle needs a durable work-order ID, runtime path, and artifacts path.
- **Purpose:** validate workshop separation and create the standard `artifacts/` and `runtime/` workbench directories.
- **Public entry:** `open_work_order.py` with required `workshop_path`; optional `project_root`, `topic`, `work_order_id`, and repeated `feature_ids`.
- **Typical usage:** call it before runtime initialization and consume the absolute paths returned as JSON.
- **Boundaries:** it creates no documents, runtime tree, feature directory, log, or Git commit; callers must not reconstruct returned paths.

## `xc-work`

[Canonical contract](../../../skills/xc-work/SKILL.md)

- **Invoke when:** governance or proportional managed effort must be selected, or persistent investigation, change, repair, review, maintenance, or cross-feature work concerns zero or more existing features.
- **Purpose:** provide direct-versus-managed classification, deterministic capability planning, the compatibility full lifecycle, and an explicit minimal adaptive managed lifecycle.
- **Public entry:** `operation=run|classify|plan|adaptive-run`, defaulting to `run`, with required `request`. `run` and `adaptive-run` require `workshop_path` and `project_root`. `plan` accepts governance, bridge-policy, scope, clarity, risk, verification, coordination, duration, audit, pace, and mode facts.
- **Classification:** execute `python skills/xc-work/scripts/classify.py [fact flags]`. Only six confirmed `no` values return direct. Any `yes` or `unknown` returns managed. Omitted facts become `unknown`; invalid input, missing executable, timeout, low-level nonzero exit, malformed JSON, or unknown schema or route always exits zero with managed `classification_status=escalated` and reason `classification-unavailable`.
- **Planning:** execute `python skills/xc-work/scripts/plan_work.py [planning facts]`. The plan monotonically derives documents, analysis, gates, implementation units, verification scopes, review, recovery, depth, and a request/bridge-bound plan receipt. Invalid or forged output fails closed to the full safe capability set.
- **Typical managed usage:** omit `operation` or use `operation=run` for the existing full lifecycle. Use explicit `adaptive-run` for a root plus sequence dynamic group whose minimal form has one combined work leaf and one finalizer; more capabilities are added only when facts require them.
- **Boundaries:** classification is read-only and performs no substantive action. The public adapter validates observable subprocess results but does not authenticate the caller, interpreter, executable bytes, or host and provides no host mediation or attestation. The strict low-level classifier retains nonzero diagnostic errors and is not a lifecycle entry. Managed work never creates or adopts a feature implicitly.

## `xc-new-feature`

[Canonical contract](../../../skills/xc-new-feature/SKILL.md)

- **Invoke when:** requested behavior requires a new explicitly managed feature.
- **Purpose:** create the feature directory, approve its three durable baselines, and govern implementation and verification in one work order.
- **Public entry:** required `workshop_path`, `project_root`, `feature_id`, and `request`; optional `auto_commit` and `document_language`.
- **Typical usage:** initialize the feature, evolve goal and baseline documents, pass approval gates, then add bounded implementation and verification nodes.
- **Boundaries:** implementation waits for baseline approval; feature documents use document evolution, and dynamic status must not be copied into `tasks.md` or `status.md`.

## `xc-feature-adoption`

[Canonical contract](../../../skills/xc-feature-adoption/SKILL.md)

- **Invoke when:** an existing unmanaged or manually developed feature needs durable managed baselines.
- **Purpose:** derive approved feature baselines from code and executable-test evidence without changing product behavior.
- **Public entry:** required `workshop_path`, `project_root`, `feature_id`, and `code_entry`; optional `request` and `document_language`.
- **Typical usage:** analyze the existing implementation, draft the three feature baselines, expose uncertainty, and obtain explicit baseline approval.
- **Boundaries:** adoption is not repair or enhancement; current behavior must not become target intent without evidence and confirmation.

## `xc-workflow-evolution`

[Canonical contract](../../../skills/xc-workflow-evolution/SKILL.md)

- **Invoke when:** portable workflow contracts, templates, agents, exports, project bridge guidance, or health checks need deliberate change.
- **Purpose:** apply the ordinary work-order and review discipline to workflow maintenance while separating portable core from project-specific policy.
- **Public entry:** required `scope`, `workshop_path`, `project_root`, and `request`; `scope` selects portable core, project bridge, agent export, orchestration template, or health check.
- **Typical usage:** confirm the six governance facts, call public `xc-work operation=classify`, and either perform only the all-`no` response-local action or enter public `xc-work operation=run` with zero features. Managed work records analysis and solution, edits canonical sources, regenerates owned outputs when required, and verifies the affected interface.
- **Boundaries:** it depends only on the `xc-work` Skill name and public parameters; it does not call another Skill's private classifier script or references. Do not hand-edit generated assets or managed runtime state; broad architectural changes require alternatives, review, and an explicit user gate.
