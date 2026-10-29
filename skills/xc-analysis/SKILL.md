---
name: "xc-analysis"
description: "Performs evidence-driven investigation, impact analysis, reconciliation, and option comparison for a managed work order. Invoke when a work order needs facts and reasoning before selecting a solution."
---

# XC Analysis

`xc-analysis` is the shared investigation contract for research, impact analysis, diagnostic evidence, feature reconciliation, and solution alternatives. Its durable work-order-level output is `analysis.md`; perspective-specific work belongs in node artifacts.

## Parameters

- `workbench_path` - `path`; required
  - Scope: Existing `.xcoding/work-orders/<work-order-id>/` workbench.
  - Side effects: Updates the work order's `analysis.md` only through a caller-owned document-evolution subtree.

- `analysis_scope` - `enum`; required
  - Allowed values: `investigation`, `reconciliation`, `diagnosis-support`, `solution-support`, `review-support`, `convention-review`.
  - Scope: Selects evidence questions and expected output dimensions. `convention-review` is the L2 deep study of project conventions surfaced by an `xc-conventions` discovery record: reconcile conflicting sources and map applicable rules to the solution and acceptance.

- `feature_ids` - `string[]`; optional
  - Scope: Existing feature baselines to reconcile. An empty list is valid.

- `inputs` - `path[]`; optional
  - Scope: User reports, feature documents, prior artifacts, code entry points, test results, and project bridge references.

## Operation

The caller reads `.xcoding/WORKFLOW.md` and `.xcoding/KNOWLEDGE.md`, opens or resumes the work order, then schedules one or more analysis nodes in its managed tree. Each node records evidence in a node artifact. A document-evolution subtree synthesizes accepted facts, hypotheses, alternatives, risks, and unresolved decisions into `analysis.md`.

For a change or repair, the analysis includes a **scope assessment**: the maturity and coupling of the existing code, the size and intent of the requested delta, whether a minimal coherent change fully satisfies the legitimate need and the task-appropriate quality bar, the viable larger options, the recommendation, and the uncertainty. If the recommendation is materially ambiguous, or a repair's correct fix would cross a design, mechanism or requirement boundary, flag it for the caller's clarification or approval gate before solution selection. A create task records its constraints and quality contract instead of a minimality assessment.

For a create task, the analysis also produces a **capability map**: compare the goal with the original request and list each user-observable capability with `source`, `priority` (`must`/`should`/`non-goal`), `user_value`, `acceptance`, and `verification`. Flag material capabilities missing from the goal, material exclusions or constraints the goal added, and any `goal-authored` exclusion without a user or project source. A narrowed goal is not self-justifying merely because the solution can satisfy it. The map is a fidelity instrument, not a breadth target: it has no minimum or maximum row count, and a small task may need only a few rows.

Use parallel nodes only for independent perspectives. The caller names each perspective, declares its artifact path, and schedules a synthesis node after all required evidence nodes complete. A synthesis may discard unsupported claims; it must not merge incompatible evidence silently.

Analysis node artifacts default to internal English. A caller may explicitly mark a user-facing analysis report with `metadata.artifact.audience=user` and `metadata.artifact.content_language=work_order.document_language`; resolve the language before writing its node-artifact frontmatter. User-facing reports follow the public `xc-document` human-readable authoring default and supplied explicit authoring requirements while preserving exact evidence.

## Output Rules

- Distinguish confirmed facts, hypotheses, and unknowns.
- Cite code, test, configuration, Git, document, or runtime-query evidence by path or command outcome.
- For feature reconciliation, compare code and executable tests as current implementation evidence against feature baselines as approved target intent.
- Evidence-backed, intent-compatible baseline drift may be synchronized through a separate document-evolution subtree.
- For change and repair, record the scope assessment and recommendation; the caller owns the scope decision and analysis must not silently choose a larger implementation.
- For create, record the capability map, the request-to-goal comparison, and every unresolved narrowing or omission. Do not silently accept a goal-authored exclusion; carry the accepted map into the solution.
- Ambiguous drift, product-intent conflict, or concurrent baseline modification requires a main-session user gate.

## Constraints

- Analysis does not modify product code or feature baselines.
- A create capability map is not a popularity list or a coverage score. Do not add capabilities without an honest user-value or request source, and do not treat a larger map as a better analysis.
- It does not infer project commands, knowledge sources, or business rules absent from the project bridge and supplied inputs. A supplied `xc-conventions` discovery record and the project locations it surfaces are inputs, not inference: analysis may read the declared C1/C2 files that record points to and reconcile them. An undeclared, repeated-in-code pattern (C3 de-facto) must stay a labeled hypothesis, never a mandatory rule, and a C1/C2 conflict or ambiguity escalates to a main-session user gate.
- It never stores detailed analysis in the runtime blackboard or reads runtime XML directly.
- Temporary scripts, intermediate outputs, and process files belong under the workbench `tmp/` directory; keep them out of the user home directory, operating-system temporary locations, and any project-repository content outside the workbench, and never declare them as artifacts.
- When the task itself requires a location outside the workbench, record the location, the reason, and the verified removal in the node artifact.
