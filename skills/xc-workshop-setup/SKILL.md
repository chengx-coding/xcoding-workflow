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

- `workshop_topology` - `string`; optional, defaults to `independent-link`
  - Allowed values: `independent-link` | `independent-nested` | `same-repo` | `no-git`.
  - Scope: How the fixed `.xcoding` path relates to the business repository. When supplied, it pins the topology without asking the user. When omitted, the Skill asks the user once, recommending `independent-link`.
  - Side effects: Determines the workshop creation command sequence, the `workshop.topology` value recorded in `.xcoding/xc-orchestration-runtime.json`, and whether a product `.gitignore` entry is appended. `independent-link` and `independent-nested` append the entry; `same-repo` and `no-git` do not.
  - Propagation: Recorded as `workshop.topology` in `.xcoding/xc-orchestration-runtime.json`, read by `xc-open-work-order` and the runtime validation. An unknown (non-allowed) value fails closed.

- `auto_commit` - `boolean`; optional, defaults to the runtime configuration
  - Scope: Controls workshop checkpoint commits.
  - Side effects: Affects terminal-node commits only.
  - Propagation: Passed through runtime configuration, not rewritten by this Skill.

## Workshop Topology

The topology is the single source of truth for how the fixed `.xcoding` path relates to the business repository. The default `independent-link` preserves current documented behavior exactly.

- `independent-link` (default): the workshop history lives in a separate Git repository outside the project, linked into the project at `.xcoding`. The product `.gitignore` ignores the `.xcoding` link target.
- `independent-nested`: the workshop history lives in an independent Git repository nested inside the project at `.xcoding`. The product `.gitignore` ignores `.xcoding`.
- `same-repo`: `.xcoding` is a plain directory versioned directly in the product repository. No `.gitignore` entry is written; the workshop state follows the product history and requires an explicit `git.auto_commit` declaration in the runtime config.
- `no-git`: `.xcoding` is a plain untracked directory with no Git repository behind it. No `.gitignore` entry is written.

### Topology and the change report

The ignore entry decides whether the workshop is part of the product's own change set, and therefore what a later change report has to explain. Under `independent-link` and `independent-nested` the product repository ignores `.xcoding/`, so the runtime tree, the node artifacts, and any feature baselines stay outside the enumeration. Under `same-repo` and `no-git` they are untracked or tracked product paths and the enumeration does contain them, including `runtime/orchestration.xml`, which every Skill in this repository forbids an agent to read. This Skill adds no workshop exclusion, so a project that runs a mutation work order must ignore `.xcoding/` or accept that its workshop is part of its own change set; the `no-git` topology may run read-only modes only. The trade-off is stated here rather than discovered later because step 0.1 is where the choice is made.

The step 0.4 `.gitignore` append happens before the project's first work order exists, so no report can cover it. The write is a single idempotent root-anchored `/.xcoding/` line, it never rewrites an existing user line, and it writes nothing for `same-repo` or `no-git`. A later work order enumerates the resulting file normally.

### Creation command sequences

Use the block for the current platform. Run a sequence only when the target `.xcoding` path does not already exist; if it already exists, inspect where it resolves and preserve that workshop instead of replacing it.

`independent-link` (independent repository outside the project plus a directory link):

POSIX shell:

```sh
PROJECT_ROOT="$(pwd)"
WORKSHOP_ROOT="$(dirname "$PROJECT_ROOT")/$(basename "$PROJECT_ROOT")-xc-workshop"
mkdir -p "$WORKSHOP_ROOT/.xcoding"
git -C "$WORKSHOP_ROOT" init
ln -s "$WORKSHOP_ROOT/.xcoding" "$PROJECT_ROOT/.xcoding"
```

Windows PowerShell:

```powershell
$ProjectRoot = (Get-Location).Path
$WorkshopRoot = Join-Path (Split-Path $ProjectRoot -Parent) "$(Split-Path $ProjectRoot -Leaf)-xc-workshop"
New-Item -ItemType Directory -Force (Join-Path $WorkshopRoot ".xcoding") | Out-Null
git -C $WorkshopRoot init
New-Item -ItemType Junction -Path (Join-Path $ProjectRoot ".xcoding") -Target (Join-Path $WorkshopRoot ".xcoding") | Out-Null
```

`independent-nested` (`git init` inside `<project>/.xcoding`):

POSIX shell:

```sh
mkdir -p "$(pwd)/.xcoding"
git -C "$(pwd)/.xcoding" init
```

Windows PowerShell:

```powershell
$ProjectRoot = (Get-Location).Path
New-Item -ItemType Directory -Force (Join-Path $ProjectRoot ".xcoding") | Out-Null
git -C (Join-Path $ProjectRoot ".xcoding") init
```

`same-repo` (plain directory versioned in the product repository):

POSIX shell:

```sh
mkdir -p "$(pwd)/.xcoding"
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force (Join-Path (Get-Location).Path ".xcoding") | Out-Null
```

`no-git` (plain untracked directory):

POSIX shell:

```sh
mkdir -p "$(pwd)/.xcoding"
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force (Join-Path (Get-Location).Path ".xcoding") | Out-Null
```

For the two independent topologies, confirm that Git reports two different top-level paths before continuing (`git -C . rev-parse --show-toplevel` and `git -C .xcoding rev-parse --show-toplevel`). For `same-repo`, confirm the product repository is the single repository. For `no-git`, confirm no Git repository backs `.xcoding`.

## Main Work Order

0. Establish the workshop topology before opening the setup work order:
   1. Determine the topology. If `workshop_topology` is supplied, use that pinned value without asking. Otherwise ask the user once, presenting `independent-link` as the recommended default and stating each topology's trade-offs (independent repositories keep workshop state out of product history; `same-repo` and `no-git` leave workshop state inside or beside the product tree). If a supplied value is not one of the four allowed values, fail closed: report it and do not proceed.
   2. Create the workshop per the chosen topology using the matching command sequence above for the current platform.
   3. Write or refresh `.xcoding/xc-orchestration-runtime.json` with `workshop.topology` set to the chosen value. If the file is missing, seed it from the runtime asset defaults `skills/xc-orchestration-runtime/assets/xc-orchestration-runtime.json` (as a content source, not a template to hand-edit) and then set the topology. When the file is present, merge the topology key and preserve all existing keys. The seeded asset also carries `report.default`, the workshop's change-report default; leave it at the asset value unless the user asks for a different one, because that value reproduces the existing mode-derived behaviour. `xc-work` owns how the tier is resolved and overridden.
   4. Append the product `.gitignore` entry for `independent-link` and `independent-nested` only by running `scripts/ensure_gitignore.py` from this Skill package with `--project-root <project_root>` and `--topology <topology>`. The script is idempotent and appends a root-anchored `/.xcoding/` entry; it never duplicates or rewrites existing user lines and reports `skipped-conflict` when the entry is already negated. For `same-repo` and `no-git`, it reports `not-applicable` and writes nothing.
1. Call `xc-open-work-order` with topic `workshop-setup`.
2. Initialize `assets/workshop-setup-template.xml` in the returned `runtime_path`.
3. Complete `prepare-workshop`, which confirms the recorded `workshop.topology` and its runtime-config entry; then embed `xc-document-evolution` under `workflow-document`.
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

- The topology default is `independent-link`; this preserves current documented behavior. `workshop_topology` pins a value for scripted or non-interactive use, and an unknown value fails closed rather than silently defaulting.
- Never fabricate project facts or a topology the user has not confirmed. If the user cannot provide required project-local facts, create a gate or leave the corresponding section explicitly unresolved; do not fabricate configuration.
- All workshop documents MUST be validated by `xc-document`.
- Document writes and validations are terminal node artifacts and follow workshop checkpoint commit rules.
- Runtime XML is accessed only through public runtime commands.
- Both POSIX and Windows command sequences are documented for every topology; use the sequence matching the current platform.
