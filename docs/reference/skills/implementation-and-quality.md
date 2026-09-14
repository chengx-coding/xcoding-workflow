# Implementation and Quality

**Language:** **English** | [简体中文](../../zh-CN/reference/skills/implementation-and-quality.md)

These supporting Skills execute approved changes and assess their evidence.

## `xc-delegation`

[Canonical contract](../../../skills/xc-delegation/SKILL.md)

- **Invoke when:** a Skill delegates one private worker role through the persistent delegated Agent and needs strict profile resolution, capability narrowing, deterministic preparation, or read-only legacy discovery.
- **Purpose:** validate Skill-local worker profiles and compile one node-attempt-bound dispatch envelope without making the private role a persistent Agent.
- **Public entry:** required `skill_root` and `profile_id`; preparation additionally requires exact runtime node/profile packets, project policy, caller constraints, adapter ID, and output path. A dynamic overlay is optional and narrowing-only.
- **Typical usage:** author a profile under the owning Skill's `assets/workers/`, validate it, obtain the exact running-attempt assignment wrapper, call `xcoding delegate prepare`, and dispatch only an authoritative envelope.
- **Boundaries:** v1 never silently falls back to legacy prompts; capability layers only narrow; runtime state and terminal authority remain runtime-owned; current host statements do not claim enforcement without pinned end-to-end evidence.

## `xc-implementation`

[Canonical contract](../../../skills/xc-implementation/SKILL.md)

- **Invoke when:** an approved solution and required gates have established one bounded implementation change.
- **Purpose:** execute exactly one runtime implementation node and record changed paths, validation, baseline impact, and residual risk.
- **Public entry:** required `workbench_path`, `work_scope`, `inputs`, and `artifact_path`.
- **Typical usage:** read the supplied node contract and approved inputs, make the smallest coherent change, run focused checks, and write the declared artifact. An adaptive minimal node may combine one coherent implementation with focused verification after its immutable plan receipt is validated.
- **Boundaries:** it does not own decomposition or retries, cannot opportunistically overwrite feature baselines, and reports only through the runtime public command.

## `xc-review`

[Canonical contract](../../../skills/xc-review/SKILL.md)

- **Invoke when:** a workflow requires independent assessment of a managed document, solution, code change, diagnosis, or verification evidence.
- **Purpose:** evaluate immutable inputs and produce traceable, severity-ranked findings and a conclusion.
- **Public entry:** required `review_kind`, `inputs`, and `artifact_path`; optional `review_context`.
- **Typical usage:** inspect the requested quality dimensions, ground each required finding in evidence, and write a validated node artifact.
- **Boundaries:** review is read-only; the caller owns remediation and risk decisions, and raw transcripts are not the default artifact.

## `xc-verification`

[Canonical contract](../../../skills/xc-verification/SKILL.md)

- **Invoke when:** implementation, diagnosis, adoption, or a feature baseline needs project-defined validation evidence.
- **Purpose:** run the smallest sufficient command set, map evidence to acceptance conditions, and record outcomes and coverage gaps.
- **Public entry:** required `workbench_path`, `verification_scope`, and `artifact_path`; optional `inputs`.
- **Typical usage:** read project verification policy, run focused checks before broader regression checks, and record every command and unexecuted prerequisite. Adaptive regression or multi-environment scopes use separate verification nodes; a fast pace never removes a required scope.
- **Boundaries:** it does not invent commands or pass criteria, silently weaken acceptance conditions, or modify product behavior to force a pass.
