---
name: "xc-analysis"
description: "Performs evidence-driven investigation, impact analysis, reconciliation, and option comparison for a managed workflow run. Invoke when a run needs facts and reasoning before selecting a solution."
---

# XC Analysis

`xc-analysis` is the shared investigation contract for research, impact analysis, diagnostic evidence, feature reconciliation, and solution alternatives. Its durable run-level output is `analysis.md`; perspective-specific work belongs in node artifacts.

## Parameters

- `run_dir` - `path`; required
  - Scope: Existing `.xcoding/runs/<run-id>/` directory.
  - Side effects: Updates the run's `analysis.md` only through a caller-owned document-evolution subtree.

- `analysis_scope` - `enum`; required
  - Allowed values: `investigation`, `reconciliation`, `diagnosis-support`, `solution-support`, `review-support`.
  - Scope: Selects evidence questions and expected output dimensions.

- `feature_ids` - `string[]`; optional
  - Scope: Existing feature baselines to reconcile. An empty list is valid.

- `inputs` - `path[]`; optional
  - Scope: User reports, feature documents, prior artifacts, code entry points, test results, and project bridge references.

## Operation

The caller reads `.xcoding/WORKFLOW.md` and `.xcoding/KNOWLEDGE.md`, creates or reuses the run, then schedules one or more analysis nodes in its managed tree. Each node records evidence in a node artifact. A document-evolution subtree synthesizes accepted facts, hypotheses, alternatives, risks, and unresolved decisions into `analysis.md`.

Use parallel nodes only for independent perspectives. The caller names each perspective, declares its artifact path, and schedules a synthesis node after all required evidence nodes complete. A synthesis may discard unsupported claims; it must not merge incompatible evidence silently.

Analysis node artifacts default to internal English. A caller may explicitly mark a user-facing analysis report with `metadata.artifact.audience=user` and `metadata.artifact.content_language=run.document_language`; resolve the language before writing its node-artifact frontmatter.

## Output Rules

- Distinguish confirmed facts, hypotheses, and unknowns.
- Cite code, test, configuration, Git, document, or runtime-query evidence by path or command outcome.
- For feature reconciliation, compare code and executable tests as current implementation evidence against feature baselines as approved target intent.
- Evidence-backed, intent-compatible baseline drift may be synchronized through a separate document-evolution subtree.
- Ambiguous drift, product-intent conflict, or concurrent baseline modification requires a main-session user gate.

## Constraints

- Analysis does not modify product code or feature baselines.
- It does not infer project commands, knowledge sources, or business rules absent from the project bridge and supplied inputs.
- It never stores detailed analysis in the runtime blackboard or reads runtime XML directly.
