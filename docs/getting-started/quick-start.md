# Quick start

**Language:** **English** | [简体中文](../zh-CN/getting-started/quick-start.md)

This guide starts from a consumer project with the required `xcoding` tool on `PATH` and at least one Agent host configured by `xcoding setup`. If either prerequisite is missing, follow [Installation](installation.md) first. Installing the wheel provides the tool; setup installs and owns the selected host's XC Skills and subagent definitions inside the explicit project root. `build_agents.py` is only the development mirror for the xcoding-workflow checkout.

## 1. Choose the consumer project

Open a terminal at the consumer project's Git root:

```console
cd /absolute/path/to/project
git rev-parse --show-toplevel
```

The remaining path examples assume this directory is the project root.

## 2. Choose the workshop topology

[`xc-workshop-setup`](../../skills/xc-workshop-setup/SKILL.md) asks once how the fixed `.xcoding` path relates to the business repository, then records the answer as `workshop.topology` in `.xcoding/xc-orchestration-runtime.json`. It recommends `independent-link`, the default that preserves the current documented behavior. For scripted or non-interactive use, pass the pinned value as the `workshop_topology` parameter to skip the question.

The four topologies are:

- `independent-link` (default): the workshop history lives in a separate Git repository outside the project, linked into the project at `.xcoding`. The product `.gitignore` ignores the `.xcoding` link target.
- `independent-nested`: the workshop history lives in an independent Git repository nested inside the project at `.xcoding`. The product `.gitignore` ignores `.xcoding`.
- `same-repo`: `.xcoding` is a plain directory versioned directly in the product repository. No `.gitignore` entry is written. Because engine checkpoint commits enter product history and work-order state follows product branches, this topology requires an explicit `git.auto_commit` declaration in the runtime config.
- `no-git`: `.xcoding` is a plain untracked directory with no Git repository behind it. No `.gitignore` entry is written and there is no checkpoint history.

Run the creation sequence matching the chosen topology below only when the project has no existing `.xcoding` path. If it already exists, inspect where it resolves and preserve that workshop instead of replacing it. For `independent-link` and `independent-nested`, setup also appends a root-anchored `/.xcoding/` entry to the product `.gitignore`; `same-repo` and `no-git` write nothing.

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

For the two independent topologies, confirm that Git reports two different top-level paths:

```console
git -C . rev-parse --show-toplevel
git -C .xcoding rev-parse --show-toplevel
```

Configure a Git identity for the workshop repository before using automatic checkpoint commits if no suitable global identity is already available.

## 3. Initialize project workflow guidance

Ask the Agent host to invoke [`xc-workshop-setup`](../../skills/xc-workshop-setup/SKILL.md) with:

```text
workshop_path: /absolute/path/to/project/.xcoding
project_root: /absolute/path/to/project
```

The setup workflow opens its own durable work order and establishes the project-specific workflow bridge and knowledge guidance. Supply real project commands, language choices, repository boundaries, and constraints when prompted. The workflow must leave unknown project facts unresolved rather than inventing them.

Complete setup before starting ordinary work or managing a feature.

## 4. Choose the first lifecycle

### Existing project work

Use [`xc-work`](../../skills/xc-work/SKILL.md) for investigation, a code change, repair, review, or maintenance. It can reference zero, one, or multiple already managed features and never creates a feature implicitly.

```text
Invoke xc-work with:
workshop_path: /absolute/path/to/project/.xcoding
project_root: /absolute/path/to/project
request: <the outcome and constraints>
mode: change
feature_ids: []
```

Select `investigation`, `change`, `repair`, `review`, or `maintenance` as the mode that matches the request.

### A genuinely new managed feature

Use [`xc-new-feature`](../../skills/xc-new-feature/SKILL.md) when the requested behavior needs a new explicit feature and approved feature baselines. Like ordinary managed work, this lifecycle mounts the change report stage: after the feature is implemented and verified it explains the feature's change set, before the feature's result document.

```text
Invoke xc-new-feature with:
workshop_path: /absolute/path/to/project/.xcoding
project_root: /absolute/path/to/project
feature_id: <stable-lowercase-slug>
request: <feature outcome, boundaries, and constraints>
```

This is the normal lifecycle that creates a new managed feature directory. Do not use it merely to label ordinary maintenance.

### Adopt an existing unmanaged feature

Use [`xc-feature-adoption`](../../skills/xc-feature-adoption/SKILL.md) when code already implements a feature but no managed baselines exist.

```text
Invoke xc-feature-adoption with:
workshop_path: /absolute/path/to/project/.xcoding
project_root: /absolute/path/to/project
feature_id: <stable-lowercase-slug>
code_entry: <existing module, interface, or path set>
request: <adoption motivation and known constraints>
```

Adoption derives evidence-backed baselines and does not silently change or repair the product. Request later product changes through a separate `xc-work`.

## 5. Let the managed lifecycle control state

Provide decisions at explicit user gates and let the runtime public interfaces own node scheduling, transitions, and checkpoints. Keep code and project commits in the project repository; keep work-order documents, feature baselines, runtime state, and node artifacts in the workshop history, which by the default `independent-link` topology is independent of the project repository.

Continue with the [documentation index](../index.md) for concepts, workflow guidance, orchestration details, and the complete Skill reference.
