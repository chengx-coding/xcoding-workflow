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

This public entry delegates writing guidance to `xc-writing`, the single owner of the shared method for human-facing prose, including non-Markdown artifacts. Invoke that Skill by its public name and parameters; do not copy its method or read its private resources from another Skill.

Map the caller's task to `xc-writing operation=write` for drafting, `operation=revise` for an explicit revision, or `operation=review` for read-only writing assessment. Pass the purpose or question as `request`, the known readership as `audience`, and existing text and evidence as tagged `inputs`: `{"kind":"text","value":"..."}` for supplied content and `{"kind":"path","value":"..."}` for an authorized file read. Identify the revision or review target separately from supporting evidence. Pass fixed content language, format constraints, and explicit user requirements through `authoring_requirements`.

Explicit user requirements override conflicting style defaults, while truthfulness, safety, required document structure, provenance, mandatory evidence, and literal accuracy remain binding. Preserve exact commands, identifiers, paths, logs, and machine output where required. Internal technical artifacts may retain specialist density for their audience. The caller still owns content and delivery; this entry does not grant permission to modify an input file.

Pure structural validation and template rendering do not invoke writing. `validate_document.py` does not claim to score or mechanically prove readability. Skills producing human-facing artifacts may continue to cite this public default and state only their format-specific additions; the writing method remains owned by `xc-writing`.

## Content Language and Audience

`content_language` is an optional simplified BCP 47 tag. When omitted, validation treats it as `en` without modifying the document. Work order lifecycles must explicitly set it from their fixed `work_order.document_language` before writing a top-level work order document.

`node-artifact` documents may additionally set `audience` to `internal` or `user`. Omitted `audience` means `internal`; internal artifacts use `en`. A user artifact must explicitly set `content_language`.

Artifact writers read `metadata.artifact.audience` and `metadata.artifact.content_language` from their supplied runtime node. The defaults are `internal` and `en`. A user artifact uses `work_order.document_language` only when the node explicitly declares that selector, and writes the resolved language tag into its frontmatter. Preserve code, paths, identifiers, commands, and raw output while localizing surrounding prose.

## Line Endings in Authored Files

Any repository text file an agent writes is stored as UTF-8 with LF line endings, and a local
edit does not rewrite unchanged lines. This applies to every authored repository text file, not
only to the managed document kinds above: source files, tests, configuration, templates, and
generated text all share the rule.

The usual way to break it is not to intend CRLF but to inherit it. On a host whose native line
terminator is CRLF, newline translation applies to every text write that does not pin its own
newline, so a three-line edit to an LF-stored file silently becomes a whole-file rewrite: the
reviewer sees every line as changed, and `git diff --check` reports one trailing-whitespace hit
per line. Nothing errors, so the damage is only visible in the diff.

Pin the newline explicitly, or write bytes. Which mechanism does that is a property of the
implementation language rather than of this contract; in Python, for example, the explicit form
is `newline="\n"` on a text write, and encoding to bytes avoids the translation layer entirely.
When a file's own format requires a different terminator, pin that one explicitly too, for the
same reason.

Verify by outcome rather than by inspection: after an edit, `git diff` should show only the
intended lines and `git diff --check` should be clean. A whole-file diff after a small edit is
this defect until proven otherwise.

## Constraints

- Frontmatter MUST NOT contain dynamic node status, task progress, loop state, or blockers.
- `tree_ref` is an opaque runtime reference. Validation does not open or inspect the referenced tree.
- Document content remains owned by the calling document-evolution node or domain Skill.
- Use templates in `assets/templates/` as starting points; replace all placeholders before validation.
- Temporary scripts, intermediate outputs, and process files belong under the workbench `tmp/` directory; keep them out of the user home directory, operating-system temporary locations, and any project-repository content outside the workbench, and never declare them as artifacts.
- When the task itself requires a location outside the workbench, record the location, the reason, and the verified removal in the node artifact.
