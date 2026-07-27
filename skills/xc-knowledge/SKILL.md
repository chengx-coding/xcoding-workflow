---
name: "xc-knowledge"
description: "Consults or maintains an optional project knowledge source according to .xcoding/KNOWLEDGE.md. Invoke only when the bridge declares a usable knowledge source or the user explicitly requests knowledge-base work."
---

# XC Knowledge

`xc-knowledge` is an optional bridge capability. It first reads `.xcoding/KNOWLEDGE.md` and follows only the locations, access method, query rules, update authority, and validation requirements declared there.

## Parameters

- `context_dir` - `path`; required
  - Scope: Project `.xcoding` directory containing `KNOWLEDGE.md`.

- `operation` - `enum`; required
  - Allowed values: `consult`, `update`, `status`.

- `topic` - `string`; optional
  - Scope: Query or update subject. Required when the bridge requires it for the chosen operation.

## Behavior

If `KNOWLEDGE.md` reports no configured knowledge base, return that fact and continue the caller's workflow using ordinary project evidence. Do not create a knowledge directory, fabricate an index, or block unrelated work.

For a configured source, use its declared access and maintenance rules. Treat retrieved material as evidence, preserve source references in the consuming analysis or artifact, and route durable knowledge updates through the bridge-defined authority.

## Constraints

- This Skill does not prescribe a storage format, directory name, provider, or ownership model.
- It does not replace `AGENTS.md`, the project workflow bridge, code, tests, or runtime artifacts as their authoritative sources.
- Knowledge updates are never implicit side effects of a feature or ordinary run.
