---
name: "xc-context-setup"
description: "Initializes a project's managed .xcoding context documents and setup run. Invoke when a project first adopts the workflow or its required context documents are missing."
---

# XC Context Setup

`xc-context-setup` establishes the required managed context documents: `.xcoding/WORKFLOW.md` and `.xcoding/KNOWLEDGE.md`. It uses `xc-run`, `xc-orchestration-runtime`, `xc-document-evolution`, and `xc-document`; it never creates a business feature.

## Parameters

### Public Parameters

- `context_dir` - `path`; required
  - Scope: Project `.xcoding` directory inside an independent context Git worktree.
  - Side effects: Creates a setup run and writes the two required context documents.
  - Propagation: Passed unchanged to `xc-run` and runtime initialization.

- `project_root` - `path`; optional, defaults to the current working directory
  - Scope: Business project root used to enforce context Git separation.
  - Side effects: Validation only.
  - Propagation: Passed unchanged to `xc-run`.

- `auto_commit` - `boolean`; optional, defaults to the runtime configuration
  - Scope: Controls context checkpoint commits.
  - Side effects: Affects terminal-node commits only.
  - Propagation: Passed through runtime configuration, not rewritten by this Skill.

## Main Run

1. Call `xc-run` with topic `workflow-setup`.
2. Initialize `assets/context-setup-template.xml` in the returned `runtime_dir`.
3. Complete `prepare-context`, then embed `xc-document-evolution` under `workflow-document`.
4. Set document blackboard values for `WORKFLOW.md`, render its template, complete validation, and complete the embedded subtree.
5. Set document blackboard values for `KNOWLEDGE.md`, embed a second document-evolution instance under `knowledge-document`, render its template, complete validation, and complete the embedded subtree.
6. Complete `finalize-context` with both documents as artifacts.

The setup main session writes project-specific body content from confirmed user decisions. It must not invent build commands, repository conventions, or knowledge-base locations.

## Context Document Requirements

`WORKFLOW.md` must define project identity, document and commit language, code repository and verification commands, feature/run conventions, and project-specific constraints.

`KNOWLEDGE.md` must state whether a knowledge base exists, where it lives, how to access it, and how to proceed when no knowledge base is configured. It must not create a knowledge directory by default.

## Constraints

- All context documents MUST be validated by `xc-document`.
- Document writes and validations are terminal node artifacts and follow context checkpoint commit rules.
- Runtime XML is accessed only through public runtime commands.
- If the user cannot provide required project-local facts, create a gate or leave the corresponding section explicitly unresolved; do not fabricate configuration.
