---
name: "xc-document"
description: "Validates and templates managed workflow Markdown documents. Invoke when a workflow creates, updates, or verifies workshop, feature, work-order, or node-artifact documents."
---

# XC Document

`xc-document` owns the structural contract for managed workflow Markdown documents. It validates YAML frontmatter, document identity, feature/work-order associations, and orchestration provenance. It does not write document content, control tree state, or decide whether a document is approved.

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

The legacy top-level fields remain available. The output also contains exactly
one normalized `receipt`:

```json
{"schema_version":1,"check":"xc-document","ok":true,"subject":"<normalized-path>","facts":{"document_kind":"node-artifact","content_language":"en","audience":"internal"}}
```

`receipt.subject` equals the normalized top-level `path`; receipt facts contain
exactly `document_kind`, `content_language`, and `audience`. A completion
caller requires process exit zero, top-level `ok=true`, and a structurally
valid receipt, then serializes and passes only `.receipt` through the runtime's
`--check-result-json`. The full validator response has extra legacy fields and
is not a valid receipt. A receipt is an unsigned caller self-report and does
not prove that this validator ran.

Validate an explicit work order language before writing `work_order.document_language`:

```powershell
python "$SKILL_DIR/scripts/validate_language.py" --language <simplified_bcp47_tag>
```

## Template Rendering

```powershell
python "$SKILL_DIR/scripts/render_document.py" `
  --template <template_path> `
  --out <document_path> `
  --set name=value `
  --set-json feature_ids='["feature-a","feature-b"]'
```

The renderer replaces only `{{snake_case}}` placeholders, rejects unresolved placeholders, and writes UTF-8 LF-normalized Markdown. Use `--set` for string values and `--set-json` for a JSON object, array, number, boolean, or null that is inserted into YAML frontmatter. Use it for deterministic scaffolding before a document-evolution worker writes the document body.

For work-order-document and node-artifact templates, the caller supplies `content_language` and every localized heading value. The renderer never detects a language or translates text.

## Managed Document Kinds

```text
project-workflow
project-knowledge
feature-contract
feature-solution
feature-verification
work-order-goal
work-order-analysis
work-order-solution
work-order-result
node-artifact
```

Every managed document uses YAML frontmatter with `schema_version: 1` and `document_kind`. Feature documents carry `feature_id` and initialization/update provenance. Work order documents carry `work_order_id`, `feature_ids`, and a main tree reference. Node artifacts carry `work_order_id`, `node_id`, feature identifiers, and a tree reference.

## Supported Frontmatter YAML

`xc-document` uses its own bounded YAML subset codec and has no external YAML
package dependency. The supported data model is sufficient for managed
frontmatter and `--set-json` values:

- String-keyed block mappings and block sequences.
- Nested flow mappings and sequences using `{...}` and `[...]`.
- Plain, single-quoted, and double-quoted strings, including standard control,
  hexadecimal, and Unicode escapes in double-quoted strings.
- Decimal integers, finite decimal or exponent floats, lowercase
  `true`/`false`, and `null`.
- Full-line and whitespace-separated inline comments outside quoted values.

Mapping insertion order is preserved. Rendering uses two-space indentation,
canonical lowercase booleans and null, finite numbers, deterministic string
quoting, and one trailing newline.

The codec rejects duplicate keys, tab indentation, indentation jumps,
non-string or complex keys, ambiguous numeric forms, malformed flow
collections or escapes, non-finite numbers, and mixed mapping/sequence
structure. General YAML extensions are outside the contract: tags, anchors,
aliases, merge keys, block scalars, directives, and multiple documents are
rejected. Frontmatter is limited to 64 KiB of UTF-8, 2,048 lines, 32 nesting
levels, 4,096 nodes, 16 KiB per scalar, and 4,096 decimal digits per integer.

## Default Human-Readable Authoring

Unless the user supplies explicit authoring requirements, managed documents intended for human use follow this default:

1. Lead with the document's purpose, conclusion, or required reader action.
2. Establish reader context before specialized terminology, interfaces, fields, or implementation details.
3. Explain necessary terms briefly at first use.
4. Remove repetition and process narration that does not help understanding or decisions.
5. Preserve material facts, constraints, evidence, risks, compatibility impact, and unresolved decisions.
6. Match technical depth to the intended audience while remaining accurate and professional.

Explicit user requirements for format, tone, length, terminology density, or audience override these style defaults. They do not override truthfulness, safety, required frontmatter or document structure, provenance, or mandatory evidence.

Preserve exact commands, identifiers, paths, logs, and machine output when literal accuracy matters. Apply the default to their surrounding explanation and summary. Internal technical artifacts may retain specialist density for their intended audience, but should still open with a concise, comprehensible summary.

This is an authoring and semantic-review contract. `validate_document.py` does not claim to score or mechanically prove readability.

## Content Language and Audience

`content_language` is an optional simplified BCP 47 tag. When omitted, validation treats it as `en` without modifying the document. Work order lifecycles must explicitly set it from their fixed `work_order.document_language` before writing a top-level work order document.

`node-artifact` documents may additionally set `audience` to `internal` or `user`. Omitted `audience` means `internal`; internal artifacts use `en`. A user artifact must explicitly set `content_language`.

Artifact writers read `metadata.artifact.audience` and `metadata.artifact.content_language` from their supplied runtime node. The defaults are `internal` and `en`. A user artifact uses `work_order.document_language` only when the node explicitly declares that selector, and writes the resolved language tag into its frontmatter. Preserve code, paths, identifiers, commands, and raw output while localizing surrounding prose.

## Constraints

- Frontmatter MUST NOT contain dynamic node status, task progress, loop state, or blockers.
- `tree_ref` is an opaque runtime reference. Validation does not open or inspect the referenced tree.
- Document content remains owned by the calling document-evolution node or domain Skill.
- Use templates in `assets/templates/` as starting points; replace all placeholders before validation.
