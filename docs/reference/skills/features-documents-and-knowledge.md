# Features, Documents, and Knowledge

[简体中文](../../zh-CN/reference/skills/features-documents-and-knowledge.md)

These supporting Skills own durable feature, document, and optional knowledge boundaries.

## `xc-feature`

[Canonical contract](../../../skills/xc-feature/SKILL.md)

- **Invoke when:** a new-feature or feature-adoption lifecycle has explicitly selected a feature identifier.
- **Purpose:** safely create one empty managed feature directory and return its authoritative path.
- **Public entry:** `manage_feature.py init` with required `workshop_path` and `feature_id`.
- **Typical usage:** initialize the directory, then create its three baselines through document-evolution subtrees.
- **Boundaries:** ordinary work cannot call it; it creates no baseline documents and rejects traversal or an existing directory.

## `xc-feature-reconciliation`

[Canonical contract](../../../skills/xc-feature-reconciliation/SKILL.md)

- **Invoke when:** an ordinary work order references an existing feature and must reconcile approved intent with current implementation evidence.
- **Purpose:** compare code and executable tests with feature baselines before selecting a change solution.
- **Public entry:** required `workbench_path`, `feature_id`, and `feature_dir`; embed its template once per related feature.
- **Typical usage:** record differences in work-order analysis, synchronize intent-compatible drift through document evolution, and gate ambiguous conflicts.
- **Boundaries:** it creates no feature, uses no locks, and treats neither code nor documents as universally authoritative.

## `xc-document`

[Canonical contract](../../../skills/xc-document/SKILL.md)

- **Invoke when:** a workflow creates, renders, or validates a managed workshop, feature, work-order, or node-artifact Markdown document.
- **Purpose:** enforce frontmatter, identity, language, audience, association, and provenance contracts.
- **Public entry:** `validate_document.py` with `document_path` and optional `expected_kind`; also exposes language validation and deterministic template rendering.
- **Typical usage:** render a template with explicit values, write the body in the resolved language, then validate the expected managed document kind.
- **Boundaries:** it does not author content, approve documents, inspect opaque tree references, or store dynamic task state in frontmatter.

## `xc-document-evolution`

[Canonical contract](../../../skills/xc-document-evolution/SKILL.md)

- **Invoke when:** managed documents need durable writing, validation, review, revision, and optional user approval.
- **Purpose:** provide the reusable orchestration subtree for the complete document lifecycle.
- **Public entry:** set the documented `document.*` blackboard values and embed `document-evolution-template.xml`.
- **Typical usage:** write, validate, loop through review and revision when enabled, pass an optional gate, and validate the final document.
- **Boundaries:** callers serialize instances sharing blackboard keys; bodies and reports stay in artifacts, and sealed-tree corrections require the owning gate and runtime reopen operation.

## `xc-knowledge`

[Canonical contract](../../../skills/xc-knowledge/SKILL.md)

- **Invoke when:** the project knowledge bridge declares a usable source or the user explicitly requests knowledge-base work.
- **Purpose:** consult, update, or report status for an optional project knowledge source under bridge-defined authority.
- **Public entry:** required `workshop_path` and `operation` (`consult`, `update`, or `status`); optional `topic`.
- **Typical usage:** read the knowledge bridge, use its declared access rules, and cite retrieved evidence in the consuming artifact.
- **Boundaries:** it prescribes no provider or storage layout, creates no default knowledge directory, and never updates knowledge implicitly.
