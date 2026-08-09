# Installation

**Language:** **English** | [简体中文](../zh-CN/getting-started/installation.md)

Install xcoding-workflow from a local checkout into the skills directory used by the consumer Agent host. The examples use `.agents/skills`; substitute the host's actual discovery directory when it differs.

## Requirements

You need Git, Python 3.12, `uv`, a matching validated prerelease `xcoding`
wheel, and an Agent host capable of discovering and invoking Skill packages.
A configured Git identity is also needed when managed workshop checkpoints are
set to create commits.

There is currently no formal Python-version or Agent-host compatibility matrix. Validate the selected Python runtime and Agent host in your environment.

## Python dependencies

XC's package uses only the Python standard library, but the package itself is
required. Runtime, Viewer, and daemon implementation lives under
`src/xcoding/`; Skills do not contain a standalone runtime fallback.
Managed-document frontmatter remains handled by the bounded YAML subset codec
shipped inside `xc-document`.

The package is not publicly published. Current cutover verification uses a
maintainer-provided validated local wheel:

```console
uv tool install /absolute/path/to/xcoding_workflow_spike-0.0.0.dev0-py3-none-any.whl
xcoding version --json
```

The tool installation must provide `xcoding`, not the retired `xc` name.
`xcoding runtime`, `xcoding viewer`, and `xcoding daemon` are the package
interfaces. Installing Skills alone is insufficient; the thin legacy runtime
adapter returns `xcoding_unavailable` when the executable is absent.

## Full-replacement consumer installation

Install the required `xcoding` tool first. The target skills directory must
already exist.

POSIX:

```sh
mkdir -p /absolute/path/to/consumer/.agents/skills
python install_skills.py --target-skills /absolute/path/to/consumer/.agents/skills
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force C:\absolute\path\to\consumer\.agents\skills | Out-Null
python install_skills.py --target-skills C:\absolute\path\to\consumer\.agents\skills
```

The root `install_skills.py` command is intentionally destructive for target XC packages:

1. It deletes every target directory whose name starts with `xc-`.
2. It removes the previous XC install manifest.
3. It installs complete canonical `xc-*` packages from the current checkout.
4. It runs a manifest-based verification of the resulting installation.

This is a **full replacement**, not a merge or an update that preserves local edits. Back up or relocate any needed target `xc-*` modifications before running it. Directories that do not start with `xc-` are not managed or removed.

## Managed drift-aware installation

For a managed target, use the installer documented by the canonical [`xc-workflow-evolution` contract](../../skills/xc-workflow-evolution/SKILL.md). It records source revision, source worktree state, the expected package set, and file hashes in a manifest inside the explicit target root.

The target root and its `skills` child must already exist:

```console
python skills/xc-workflow-evolution/scripts/install_xc_skills.py --source-root /absolute/path/to/xcoding-workflow --target-root /absolute/path/to/consumer/.agents --manifest /absolute/path/to/consumer/.agents/.xc-skill-install-manifest.json
```

Verify the source, manifest, and installed packages without writing:

```console
python skills/xc-workflow-evolution/scripts/install_xc_skills.py --source-root /absolute/path/to/xcoding-workflow --target-root /absolute/path/to/consumer/.agents --manifest /absolute/path/to/consumer/.agents/.xc-skill-install-manifest.json --check
```

On later installs, the managed installer first compares the target against its existing manifest. It refuses changed or missing files, unexpected files, and unexpected `xc-*` packages rather than overwriting drift. If no manifest exists, it refuses a target that already contains unmanaged `xc-*` packages. Once those gates pass, it replaces the complete managed package set and removes only stale `xc-*` packages recorded by the previous manifest. Non-`xc-*` packages remain outside its ownership.

An installation created by the root installer already has a compatible manifest, so later updates may use the drift-aware command directly.

## Consumer install versus development mirror

Use `install_skills.py` or the managed installer for a consumer project. Do not use `build_agents.py` as a consumer installation command.

`build_agents.py` is a repository-development helper. It mirrors canonical packages from this checkout's `skills/` directory into this same checkout's local Agent discovery directory. It exists so contributors can test canonical source changes locally; it does not target another project and does not establish a managed consumer manifest.

Continue with the [quick start](quick-start.md) to create the independent workshop and initialize its project-specific documents.
