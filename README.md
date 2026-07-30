# xcoding-workflow

**Language:** **English** | [Simplified Chinese (简体中文)](README.zh-CN.md)

xcoding-workflow is the canonical source for a portable, Skill-driven Agent coding workflow. It covers discovery, design, implementation, diagnosis, verification, review, repair, and delivery without tying the workflow to one programming language, framework, or Agent host.

## Core model

- Canonical `xc-*` Skill packages define public workflow entry points and reusable services.
- Each consumer project exposes a fixed `.xcoding` workshop backed by a Git worktree that is independent from the project's source repository.
- Durable work runs as a work order. Runtime orchestration owns scheduling and state; concise blackboard values coordinate decisions, while documents and other substantial evidence remain artifacts.
- Managed features are explicit. Use the new-feature workflow to create one, the adoption workflow to baseline existing code, and the ordinary work workflow for changes that may relate to zero, one, or multiple existing features.

## Prerequisites

- Git, including a configured identity when workshop checkpoint commits are enabled.
- Python and `pip` to run the repository scripts and install [the declared dependencies](requirements.txt).
- An Agent host that can discover and invoke installed Skill packages.

The project does not yet publish a formal Python-version or Agent-host compatibility matrix. Validate the workflow with the Python runtime and host used in your environment.

## Install the Skills

From a checkout of this repository, install its Python dependencies:

```console
python -m pip install -r requirements.txt
```

Create the consumer host's target skills directory, then run the root installer:

```console
python install_skills.py --target-skills /absolute/path/to/consumer/.agents/skills
```

**This command performs a full replacement of the target `xc-*` package set.** It deletes every directory whose name starts with `xc-` from the target skills directory, removes the previous XC install manifest, and installs complete packages from this checkout. Local changes inside target `xc-*` packages are not preserved. Packages that do not start with `xc-` are left untouched.

For managed updates that must detect drift before replacing packages, use the installer owned by [`xc-workflow-evolution`](skills/xc-workflow-evolution/SKILL.md):

```console
python skills/xc-workflow-evolution/scripts/install_xc_skills.py --source-root /absolute/path/to/xcoding-workflow --target-root /absolute/path/to/consumer/.agents --manifest /absolute/path/to/consumer/.agents/.xc-skill-install-manifest.json
python skills/xc-workflow-evolution/scripts/install_xc_skills.py --source-root /absolute/path/to/xcoding-workflow --target-root /absolute/path/to/consumer/.agents --manifest /absolute/path/to/consumer/.agents/.xc-skill-install-manifest.json --check
```

The managed installer copies complete packages, preserves non-`xc-*` packages, records source and file hashes, and refuses changed, missing, or unexpected target `xc-*` content. A first managed install requires a clean target with no unmanaged `xc-*` packages; an installation created by the root installer already has the required manifest.

## Create the workshop

Run these commands from the consumer project's root only when `.xcoding` does not already exist. They create a separate workshop repository beside the project and expose its workshop directory at the fixed project path.

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

Do not replace an existing `.xcoding` path without first identifying and preserving the workshop it references.

## Start managed work

First invoke [`xc-workshop-setup`](skills/xc-workshop-setup/SKILL.md) with the consumer project root and its `.xcoding` workshop. It establishes the project-specific workflow bridge and knowledge guidance without inventing project commands or conventions.

Then invoke one lifecycle entry point:

- [`xc-work`](skills/xc-work/SKILL.md) for investigation, iteration, repair, review, maintenance, or cross-feature work.
- [`xc-new-feature`](skills/xc-new-feature/SKILL.md) to create a new explicitly managed feature and its approved baselines.
- [`xc-feature-adoption`](skills/xc-feature-adoption/SKILL.md) to derive managed baselines for an existing unmanaged feature before future changes.

Agent-host invocation syntax varies. Pass the public parameters documented by the selected Skill, including `workshop_path` and `project_root`.

## Documentation

- [Documentation index](docs/index.md)
- [Installation](docs/getting-started/installation.md)
- [Quick start](docs/getting-started/quick-start.md)

Consumer installation is separate from `build_agents.py`. That development helper mirrors this repository's canonical `skills/` tree into this checkout's local Agent discovery directory; it is not the consumer installer.

## License

Released under the [MIT License](LICENSE).
