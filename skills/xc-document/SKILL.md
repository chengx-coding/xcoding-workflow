---
name: "xc-document"
description: "Validates and templates managed workflow Markdown documents. Invoke when a workflow creates, updates, or verifies context, feature, run, or node-artifact documents."
---

# XC Document

`xc-document` owns the structural contract for managed workflow Markdown documents. It validates YAML frontmatter, document identity, feature/run associations, and orchestration provenance. It does not write document content, control tree state, or decide whether a document is approved.

## Parameters

### Public Parameters

- `document_path` - `path`; required
  - Scope: Markdown document to validate.
  - Side effects: Read-only validation.
  - Propagation: No downstream propagation.

- `expected_kind` - `enum`; optional
  - Scope: Requires the document to use a specific managed `document_kind`.
  - Side effects: Read-only validation.
  - Propagation: No downstream propagation.

## Operation

```powershell
python "$SKILL_DIR/scripts/validate_document.py" `
  --document <document_path> `
  --expected-kind <document_kind>
```

The validator emits JSON and returns nonzero for invalid frontmatter or an invalid document contract.

## Template Rendering

```powershell
python "$SKILL_DIR/scripts/render_document.py" `
  --template <template_path> `
  --out <document_path> `
  --set name=value `
  --set-json feature_ids='["feature-a","feature-b"]'
```

The renderer replaces only `{{snake_case}}` placeholders, rejects unresolved placeholders, and writes UTF-8 LF-normalized Markdown. Use `--set` for string values and `--set-json` for a JSON object, array, number, boolean, or null that is inserted into YAML frontmatter. Use it for deterministic scaffolding before a document-evolution worker writes the document body.

## Managed Document Kinds

```text
project-workflow
project-knowledge
feature-contract
feature-solution
feature-verification
run-goal
run-analysis
run-solution
run-result
node-artifact
```

Every managed document uses YAML frontmatter with `schema_version: 1` and `document_kind`. Feature documents carry `feature_id` and initialization/update provenance. Run documents carry `run_id`, `feature_ids`, and a main tree reference. Node artifacts carry `run_id`, `node_id`, feature identifiers, and a tree reference.

## Constraints

- Frontmatter MUST NOT contain dynamic node status, task progress, loop state, or blockers.
- `tree_ref` is an opaque runtime reference. Validation does not open or inspect the referenced tree.
- Document content remains owned by the calling document-evolution node or domain Skill.
- Use templates in `assets/templates/` as starting points; replace all placeholders before validation.
