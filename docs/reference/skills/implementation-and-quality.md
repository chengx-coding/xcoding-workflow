# Implementation and Quality

**Language:** **English** | [简体中文](../../zh-CN/reference/skills/implementation-and-quality.md)

These supporting Skills execute approved changes, guide technical writing, and assess evidence.

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
- **Typical usage:** read the supplied node contract and approved inputs, implement the accepted scope with the minimum sufficient magnitude for the task (`create` maximizes within its quality contract; `change` uses the minimum sufficient change; `repair` keeps the strong minimality presumption), run focused checks, and write the declared artifact. For `create`, the accepted capability matrix is part of the accepted scope: implement every accepted must capability and do not silently drop or weaken a must/should capability. If the accepted scope or a must capability proves insufficient, stop and return to the caller instead of expanding or shrinking it. An adaptive minimal node may combine one coherent implementation with focused verification after its immutable plan receipt is validated.
- **Boundaries:** it does not own decomposition or retries, cannot opportunistically overwrite feature baselines, and reports only through the runtime public command. Scope expansion or shrink is a caller or gate decision, not a worker decision.

## `xc-visual-design`

[Canonical contract](../../../skills/xc-visual-design/SKILL.md)

- **Invoke when:** visual quality is part of a rendered deliverable's acceptance, or the project bridge declares a visual target.
- **Purpose:** own the visual brief and independent critic loop. It does not own a style, palette, score, or a functional capability list.
- **Public entry:** `workbench_path`, `brief_path`, `review_path`, `screenshots`; optional `functional_evidence`. The functional-preservation evidence is owned by `xc-verification`.
- **Method boundary:** the target comes from the request/bridge; no fixed visual dimensions; independent critic required; unresolved high findings or a failed functional gate block acceptance.

## `xc-writing`

[Canonical contract](../../../skills/xc-writing/SKILL.md)

- **Invoke when:** drafting a human-facing technical answer, explanation, document, or report; revising difficult prose; or reviewing clarity while preserving meaning.
- **Purpose:** help readers understand objects, reasoning, and choices while preserving facts, conditions, exceptions, normative strength, and uncertainty. It owns the shared writing method for documents and standalone answers.
- **Public entry:** required `request`; `operation=write|revise|review` defaults to `write`; optional `inputs`, `audience`, and `authoring_requirements`. Each input is an object with `kind=text|path` and a non-empty string `value`; bare strings are not inferred as paths. Revision and review require identifiable target text.
- **Typical usage:** give the current question or writing task and source material, adapt the explanation to the reader, then check the result against its evidence. For example, set `operation=revise` and pass `inputs=[{"kind":"text","value":"The draft is visible only to its author."}]` to revise supplied text without reading a file. Review returns evidence-backed writing findings and local suggestions without editing the source.
- **Boundaries:** it does not replace managed-document structure validation, the document lifecycle, overall quality review, or the caller's authorization. Missing or ambiguous source material is reported rather than invented. User style and language requirements apply; commands, evidence, and material constraints stay exact. It adds no persistent mode, readability score, ISO conformity claim, or guarantee about every future reply or reader.

## `xc-review`

[Canonical contract](../../../skills/xc-review/SKILL.md)

- **Invoke when:** a workflow requires independent assessment of a managed document, solution, code change, diagnosis, or verification evidence.
- **Purpose:** evaluate immutable inputs and produce traceable, severity-ranked findings and a conclusion.
- **Public entry:** required `review_kind`, `inputs`, and `artifact_path`; optional `review_context`.
- **Typical usage:** inspect the requested quality dimensions, ground each required finding in evidence, and write a validated node artifact. When an experience product supplies its proposed overlay checks, include first-run discoverability, the `xc-visual-design` review artifacts when visual quality is in acceptance, state-dependent backdrop and progression; do not infer the overlay from a merely visual surface. For code and solution reviews, also check under-scope (the accepted need or quality bar is not met), over-scope (unnecessary churn or changes beyond the approved scope), and scope drift (the implementation differs from the recorded scope decision). For `create`, check fidelity against the original request plus the accepted capability matrix, not only the approved solution; a material exclusion with no user or project source is an unsourced narrowing. When a reference signature was recorded, a missing or weak signature must capability is under-scope; a signature should capability is under-scope unless the accepted matrix records its deferral with reason and impact; importing unrelated reference features is over-scope. When a prior capability inventory was supplied, an unexplained missing capability is a finding; replace/retire needs its recorded reason, impact and source, and a prior should may be accepted as defer only with reason, impact, source and a re-entry trigger. For interactive visual experience products, the first-run affordance and visual-state backdrop are visual-row musts.
- **Boundaries:** review is read-only; the caller owns remediation and risk decisions, and raw transcripts are not the default artifact. Scope findings are evidence-backed review judgments, not a mechanical scope checker.

## `xc-verification`

[Canonical contract](../../../skills/xc-verification/SKILL.md)

- **Invoke when:** implementation, diagnosis, adoption, or a feature baseline needs project-defined validation evidence.
- **Purpose:** run the smallest sufficient command set, map evidence to acceptance conditions, and record outcomes and coverage gaps.
- **Public entry:** required `workbench_path`, `verification_scope`, and `artifact_path`; optional `inputs`.
- **Typical usage:** read project verification policy, run focused checks before broader regression checks, and record every command and unexecuted prerequisite. For an experience product, execute first-run discoverability, the `xc-visual-design` review artifacts when visual quality is in acceptance, state-dependent backdrop and progression checks. For `create`, map evidence to every must/should capability in the accepted matrix using the output-surface profile selected by analysis; a passing test suite does not prove an unverified capability. For a visual surface, use the visual profile's visible-state/multi-state checks; for CLI/API/file or docs surfaces, use their own evidence and do not require screenshots. Adaptive regression or multi-environment scopes use separate verification nodes; a fast pace never removes a required scope. For interactive visual experience products, the first-run affordance and visual-state backdrop are visual-row musts.
- **Boundaries:** it does not invent commands or pass criteria, silently weaken acceptance conditions, or modify product behavior to force a pass.

## Experience-product overlay

`experience-quality` is a proposed task-class overlay. It records experience gaps for the requested
product; visual quality is delegated to `xc-visual-design`, and functional evidence to
`xc-verification`. The overlay does not own a style or a universal score.
