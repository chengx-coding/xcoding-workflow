# Quick start

[简体中文](../zh-CN/getting-started/quick-start.md)

This guide starts from a consumer project whose Agent host can discover the installed `xc-*` Skill packages. If the packages are not installed, follow [Installation](installation.md) first. Consumer installation uses `install_skills.py` or the managed installer; `build_agents.py` is only the development mirror for the xcoding-workflow checkout.

## 1. Choose the consumer project

Open a terminal at the consumer project's Git root:

```console
cd /absolute/path/to/project
git rev-parse --show-toplevel
```

The remaining path examples assume this directory is the project root.

## 2. Create an independent workshop

The fixed project path `.xcoding` must resolve inside a Git worktree whose repository root differs from the project repository root. Do not place the workshop history in the business source repository.

Run one of the following blocks only when the project has no existing `.xcoding` path. If it already exists, inspect where it resolves and preserve that workshop instead of replacing it.

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

Confirm that Git reports two different top-level paths:

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

Use [`xc-new-feature`](../../skills/xc-new-feature/SKILL.md) when the requested behavior needs a new explicit feature and approved feature baselines.

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

Provide decisions at explicit user gates and let the runtime public interfaces own node scheduling, transitions, and checkpoints. Keep code and project commits in the project repository; keep work-order documents, feature baselines, runtime state, and node artifacts in the independent workshop history.

Continue with the [documentation index](../index.md) for concepts, workflow guidance, orchestration details, and the complete Skill reference.
