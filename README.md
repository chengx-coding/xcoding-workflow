# xcoding-workflow

**Language:** **English** | [简体中文](README.zh-CN.md)

xcoding-workflow helps coding agents carry work from an initial request to a tested, reviewed result. It works across programming languages, frameworks, and the applications that run coding agents, known here as **Agent hosts**.

## What It Does

- XC is installed as a set of workflow modules called **Skills**.
- Small, low-risk tasks can be completed directly.
- Work that needs a plan, review, recovery, or a durable record runs as a **managed work order**. A work order keeps the goal, decisions, progress, and evidence together.
- An explicitly adaptive managed work order can start with one combined work leaf and one finalizer, then add documents, analysis, gates, verification, review, and recovery as confirmed facts require.
- The `.xcoding` directory is the project's workflow workspace. It is kept in a separate Git worktree, which is a separate working directory for workflow history, so those records do not mix with source-code history.
- Long-lived product features are managed only when you explicitly create or adopt them. Ordinary maintenance does not create a feature automatically.

## Choose Direct Or Managed Work

Before changing anything, XC decides whether the task is safe to finish as a one-off action. It asks six questions:

1. Must progress or evidence be kept for later?
2. Could the task affect shared code, a public contract, data, permissions, security, infrastructure, or a release?
3. Is a complete one-step rollback unavailable?
4. Must the task wait, restart, or continue in another session?
5. Must multiple people, agents, or external systems coordinate?
6. Is a retained review, approval, verification, or audit record required?

Each answer is `yes`, `no`, or `unknown`.

- Use **direct work** only when all six answers are confirmed `no`.
- Use a **managed work order** when any answer is `yes`, `unknown`, or cannot be checked.

Project rules may require managed work even when the general rules allow direct work. If new information appears during a direct task, answer the six questions again before continuing.

### Automation

The public classifier is:

```console
python skills/xc-work/scripts/classify.py [fact flags]
```

Its six flags are `needs_persistence`, `material_impact`, `difficult_rollback`, `crosses_sessions`, `multiple_actors`, and `audit_required`. Omitted flags become `unknown`. Invalid input, timeouts, execution failures, and invalid output all produce a managed result instead of silently allowing direct work.

Use [`xc-work`](skills/xc-work/SKILL.md) with `operation=run` to start managed work. This operation is always managed. Model name, vendor, context-window size, and project technology never change the six answers or remove required review and verification.

`operation=adaptive-run` is an explicit managed alternative. It preserves a durable runtime while allowing a minimal workbench with no mandatory top-level documents. `operation=plan` derives monotonic capabilities from governance, project policy, scope, clarity, risk, verification, coordination, duration, audit, and `adaptive|fast|thorough` pace facts. Existing omitted or explicit `run` behavior remains the full lifecycle.

## Prerequisites

- Git. Configure a Git identity if you want XC to save automatic workflow checkpoints.
- Python to run the repository scripts. XC has no third-party Python runtime package dependency.
- An Agent host that can load and run Skill packages.

The project does not yet publish a formal Python-version or Agent-host compatibility matrix. Validate the workflow with the Python runtime and host used in your environment.

## Install XC

Choose the directory where your Agent host loads Skills, create it if needed,
and install XC into it:

```console
python install_skills.py --target-skills /absolute/path/to/consumer/.agents/skills
```

**This command replaces every existing package whose name starts with `xc-`.** Local changes inside those packages are deleted. Packages with other names are not changed.

For later updates, the following installer can detect local changes before replacing files:

```console
python skills/xc-workflow-evolution/scripts/install_xc_skills.py --source-root /absolute/path/to/xcoding-workflow --target-root /absolute/path/to/consumer/.agents --manifest /absolute/path/to/consumer/.agents/.xc-skill-install-manifest.json
python skills/xc-workflow-evolution/scripts/install_xc_skills.py --source-root /absolute/path/to/xcoding-workflow --target-root /absolute/path/to/consumer/.agents --manifest /absolute/path/to/consumer/.agents/.xc-skill-install-manifest.json --check
```

It records which XC files were installed. The `--check` form reports changed, missing, or unexpected files without replacing them. Run the root installer once before using this update path so the installation record exists.

## Create the Workflow Workspace

XC stores plans, progress, decisions, and evidence in `.xcoding`. Keep that directory in a separate Git repository so workflow history does not mix with source-code history.

Run one of the following examples from your project root only when `.xcoding` does not already exist. The commands create a sibling repository and connect its `.xcoding` directory to the project.

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

If `.xcoding` already exists, find out what it points to and preserve that workspace instead of replacing it.

## Start Your First Managed Task

Run [`xc-workshop-setup`](skills/xc-workshop-setup/SKILL.md) once. Give it the project root and the `.xcoding` path. It records the project's real build, test, documentation, and commit rules.

Then choose one entry point:

- [`xc-work`](skills/xc-work/SKILL.md) for ordinary investigation, repair, review, or maintenance.
- [`xc-new-feature`](skills/xc-new-feature/SKILL.md) when you are starting a long-lived product feature and want XC to manage it explicitly.
- [`xc-feature-adoption`](skills/xc-feature-adoption/SKILL.md) when an existing feature should become managed before future changes.

Agent hosts use different invocation syntax. Follow your host's normal Skill syntax and pass the `project_root` and `workshop_path` parameters documented by the selected entry point.

## Documentation

- [Documentation index](docs/index.md)
- [Installation](docs/getting-started/installation.md)
- [Quick start](docs/getting-started/quick-start.md)

`build_agents.py` is only for developing this repository. It refreshes this checkout's local Skill mirror; it does not install XC into another project.

## License

Released under the [MIT License](LICENSE).
