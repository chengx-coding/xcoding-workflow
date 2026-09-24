# Implementation and Quality

**Language:** **English** | [简体中文](../../zh-CN/reference/skills/implementation-and-quality.md)

These supporting Skills execute approved changes, explain them to human reviewers, and assess their evidence.

## `xc-change-report`

[Canonical contract](../../../skills/xc-change-report/SKILL.md)

- **Invoke when:** a work order changed analysable code and a human must review that change without opening an IDE: after implementation and verification, and before the result document.
- **Purpose:** turn one work order's change set into a single self-contained offline HTML report plus the coverage manifest that proves every analysable change unit is covered by an analysis, bound to the code it cites, of what changed, why it exists, the design it embodies, and its place in the larger flow. A unit may additionally declare a change class and answer the design dimensions that class requires (motivation, before/after, alternatives, lifecycle, upstream callers and downstream callees, trade-offs, impact), and carry structured depth blocks (a before/after step table, a lifecycle table, or a caller/callee table), so the report reads top-down from design intent to concrete implementation; those dimensions are validated for presence and structure, not for correctness. Following a prefer-diagrams default, the caller/callee and before/after depth blocks also derive layered call-graph and before/after flow diagrams automatically, sequence interactions may use an optional deterministic SVG carrier, and a change class for which a diagram is the best expression but which carries none earns a non-blocking advisory rather than a failure.
- **Public entry:** required `report_path`, `manifest_path`, `repo_path`, `baseline_commit`, `language`, and `strength`; validation additionally requires `stage`, and `verdicts_path` is required at the final stage; `gate_required` defaults to `false`. The two baseline snapshot directories `baseline_worktree_dir` and `baseline_untracked_dir` are required in practice, because the validator recomputes the baseline digest from the recorded snapshot instead of from the live worktree. The package's own capture command produces them: `python skills/xc-change-report/scripts/capture_baseline.py --repo <repo> --workbench <workbench> --work-order-id <id> [--baseline-worktree-dir <dir>] [--baseline-untracked-dir <dir>] [--format json|keys]`, whose second `--verify-existing` form recomputes the recorded digest from the recorded worktree snapshot, re-verifies the recorded counts against git and the two recorded snapshots, and fails closed on any mismatch, all without materialising either directory again.
- **Typical usage:** capture the baseline while the worktree is still at its opened state, before implementation touches it: run the capture form once at work order open, which mirrors the tracked paths into `<workbench>/tmp/baseline-worktree/` and the untracked paths into `<workbench>/tmp/baseline-untracked/`, and records both directories with the worktree digest in `<workbench>/tmp/baseline-open-state.json`. Then enumerate the change set and publish the manifest, build the skeleton, write the eight required analysis fields for every unit the manifest lists (several units may share one analysis when it declares that it covers all of them), then validate at `stage=coverage` and again at `stage=final` after the accuracy review. Every round regenerates the same single report; a report that went stale after code rework is refreshed instead of failing a node, and the refresh loop is bounded.
- **Boundaries:** it never edits code and reaches no acceptance decision about the change; the strength tier changes content thickness only, because all three tiers run every mechanical check and the accuracy review; the human gate is optional and closed by default; hash and token checks prove that an analysis is bound to the code it cites, not that it is correct, and the accuracy review that judges meaning can itself be wrong.

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
