---
name: "xc-workshop-setup"
description: "Initializes a project's managed .xcoding workshop documents and setup work order. Invoke when a project first adopts the workflow or its required workshop documents are missing."
---

# XC Workshop Setup

`xc-workshop-setup` establishes the required managed workshop documents: `.xcoding/WORKFLOW.md` and `.xcoding/KNOWLEDGE.md`. It uses `xc-open-work-order`, `xc-orchestration-runtime`, `xc-document-evolution`, and `xc-document`; it never creates a business feature.

## Parameters

### Public Parameters

- `workshop_path` - `path`; required
  - Scope: Project `.xcoding` workshop inside an independent workshop Git worktree.
  - Side effects: Opens a setup work order and writes the two required workshop documents.
  - Propagation: Passed unchanged to `xc-open-work-order`.

- `project_root` - `path`; optional, defaults to the current working directory
  - Scope: Business project root used to enforce workshop Git separation.
  - Side effects: Validation only.
  - Propagation: Passed unchanged to `xc-open-work-order`.

- `auto_commit` - `boolean`; optional, defaults to the runtime configuration
  - Scope: Controls workshop checkpoint commits.
  - Side effects: Affects terminal-node commits only.
  - Propagation: Passed through runtime configuration, not rewritten by this Skill.

## Main Work Order

1. Call `xc-open-work-order` with topic `workshop-setup`.
2. Initialize `assets/workshop-setup-template.xml` in the returned `runtime_path`.
3. Complete `prepare-workshop`, then embed `xc-document-evolution` under `workflow-document`.
4. Set document blackboard values for `WORKFLOW.md`, render its template, complete validation, and complete the embedded subtree.
5. Set document blackboard values for `KNOWLEDGE.md`, embed a second document-evolution instance under `knowledge-document`, render its template, complete validation, and complete the embedded subtree.
6. Complete `finalize-workshop` with both documents as artifacts.

When the runtime reports an empty reachable dynamic group, append the planned
document subtree or close the group through the public runtime command before
requesting unrelated work.

The setup main session writes project-specific body content from confirmed user decisions. It must not invent build commands, repository conventions, or knowledge-base locations.

## Workshop Document Requirements

`WORKFLOW.md` must define project identity, project-document and commit language, code repository and verification commands, feature/work-order conventions, and project-specific constraints. It decides the language of project workflow, knowledge, and feature-baseline documents; top-level work order documents instead use their fixed `work_order.document_language`.

`KNOWLEDGE.md` must state whether a knowledge base exists, where it lives, how to access it, and how to proceed when no knowledge base is configured. It must not create a knowledge directory by default.

## Constraints

- All workshop documents MUST be validated by `xc-document`.
- Document writes and validations are terminal node artifacts and follow workshop checkpoint commit rules.
- Runtime XML is accessed only through public runtime commands.
- If the user cannot provide required project-local facts, create a gate or leave the corresponding section explicitly unresolved; do not fabricate configuration.
