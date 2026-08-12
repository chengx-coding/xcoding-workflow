# Installation

**Language:** **English** | [简体中文](../zh-CN/getting-started/installation.md)

Install a supported XC release by verifying its immutable GitHub Release wheel, installing the `xcoding` tool with `uv`, and letting `xcoding setup` manage the selected Agent hosts inside one explicit consumer project. The package does not provide installer wrappers or a separate Skill-install command for the supported path.

## Release and support matrix

The first supported distribution contract is `xcoding-workflow 0.1.0` with the single console command `xcoding`. A public release is supported only after its immutable GitHub Release contains the wheel and the matching integrity and provenance files. XC is not published on PyPI.

| Surface | `0.1.0` contract | Evidence boundary |
| --- | --- | --- |
| Operating system | Windows x86_64 | This is the only formally supported platform. |
| Python | CPython `>=3.12`; formal baseline CPython `3.12.13` | Windows CPython `3.14.3` may have release smoke evidence, but an accepted newer version is not the formal baseline. Non-CPython is unsupported. |
| Codex | Codex CLI `0.145.0` on Windows x86_64 | Release evidence must prove actual Skill and subagent discovery, loading, and execution. Executable detection alone is insufficient. |
| OpenCode | OpenCode `1.18.9` on Windows x86_64 | The same real discovery, loading, and execution requirement applies. |
| Claude Code | Claude Code `2.1.162` on Windows x86_64 | The same real discovery, loading, and execution requirement applies. |
| Trae | Trae CN `1.107.1` x64 on Windows x86_64 | The same real discovery, loading, and execution requirement applies. |
| WSL | WSL2 Ubuntu 26.04 LTS x86_64 with CPython `3.14.4` | Experimental compatibility smoke evidence only; this does not establish native Linux support. |
| Native Linux and macOS | Unsupported for `0.1.0` | macOS is deferred. Future support requires a separately approved contract and real candidate evidence. |

The table defines the release gate, not a claim that an unpublished candidate has passed. If the immutable release and its bound evidence are absent, there is no supported public `0.1.0` artifact.

## Obtain and verify the tool

Download the wheel, `SHA256SUMS`, `provenance.json`, `integrity-manifest.json`, `release-notes.en.md`, and `release-notes.zh-CN.md` from the same immutable GitHub Release. Before installation, verify that the wheel name, size, digest, distribution version, project commit, and Bundle digest match those release files. Candidate-specific hashes belong to the release assets and are intentionally not copied into these project documents.

Install the verified local wheel:

```console
uv tool install /absolute/path/to/xcoding_workflow-0.1.0-py3-none-any.whl
xcoding version --json
xcoding doctor --json
```

The installation creates `xcoding`; there is no `xc` alias. XC does not distribute `install.ps1`, `install.sh`, remote-script pipe commands, or compatibility wrappers. Do not install a similarly named package from PyPI.

## Configure Agent hosts in a project

Run setup with an explicit existing project root and at least one explicit host. Repeat `--host` for every host that should remain installed:

```console
xcoding setup --project-root /absolute/path/to/project --host codex --host opencode --host claude-code --host trae
```

Host identifiers and project-relative targets are fixed:

| Host ID | Subagent definitions | XC Skills |
| --- | --- | --- |
| `codex` | `.codex/agents` | `.agents/skills` |
| `opencode` | `.opencode/agents` | `.agents/skills` |
| `claude-code` | `.claude/agents` | `.claude/skills` |
| `trae` | `.trae/agents` | `.agents/skills` |

The host set is complete desired state, not an incremental add list. Repeating a host is harmless. On a later successful setup, adding a host installs its mapping; omitting a previously selected host removes only unchanged paths owned solely by that host. Shared Skills remain while any selected host owns them.

Setup never infers the project from the current directory, detects hosts automatically, adopts unmanaged files, or accepts a force option.

## Inspect before writing

Add `--dry-run` to execute Bundle validation, project-root and path safety checks, conflict detection, ownership planning, and lock acquisition without changing the project:

```console
xcoding setup --project-root /absolute/path/to/project --host codex --host trae --dry-run
```

The dry run reports create, replace, remove, and unchanged operations and always returns `writes_performed: false`. Setup fails closed before mutation when the Bundle is invalid, the project root or lock cannot be proven, a target crosses a link or reparse point, an unmanaged target conflicts, a managed file has drifted, or unexpected setup state exists. Resolve the reported ownership or path issue; do not overwrite it manually and retry blindly.

## Managed upgrades and state

Ordinary setup performs first installation and managed upgrade through one staged transaction. It verifies all desired bytes before touching targets, records intent durably, uses atomic replacement, and publishes the ownership manifest only after target operations succeed. An interrupted transaction leaves durable state for explicit recovery rather than pretending that partial work succeeded.

Project-local transaction state is under `.agents/.xcoding-setup/`:

- `manifest.json` records the successful generation, desired host set, Bundle identity, managed paths, hashes, and shared owners.
- `journal.json` records an in-progress transaction and is present only when recovery may be required.
- `staging/` and generation backups hold package-owned transaction data needed for safe completion or rollback.

Do not edit or delete these files to bypass a failure. Setup removes only paths that its manifest owns and whose current identity still matches the recorded managed bytes. Unmanaged files and drift remain user-owned conflicts.

## Recovery and rollback

If setup reports `recovery_required`, close the interrupted journal explicitly:

```console
xcoding setup --project-root /absolute/path/to/project --recover
```

Recovery inspects the durable journal and either completes a transaction whose manifest was already committed or restores the prior generation. It is idempotent for the same recoverable state and does not accept `--host` or `--dry-run`.

To restore the immediately preceding successful generation, use:

```console
xcoding setup --project-root /absolute/path/to/project --rollback
```

Rollback also rejects `--host` and `--dry-run`. It is available only when a valid previous generation exists and no open journal requires recovery. Neither operation deletes unowned files or overwrites drifted managed bytes. A lock, identity, journal, backup, or rollback failure remains a machine-readable error that requires diagnosis; it is never converted into a best-effort destructive cleanup.

## Release and maintenance policy

GitHub Releases are the only release channel for `0.1.0`; PyPI, private indexes, remote install scripts, and alternate registries are outside this contract. A release must bind one immutable tag, project commit, wheel digest, Bundle digest, exact asset set, support-matrix evidence, and bilingual release notes. Publication occurs only after the candidate gates pass and a user explicitly approves release; these installation documents do not authorize publication.

Maintenance is best effort for the latest `0.1.x` patch only. There is no service-level agreement and no guaranteed backport to older patches. A change that breaks a documented public contract belongs in `0.2.0` or another later minor version rather than a `0.1.x` patch. If a new support line replaces `0.1.x` or maintenance ends, the release notes must announce the migration or end-of-support boundary and retain rollback guidance in both languages.

Continue with the [quick start](quick-start.md) to create the independent workshop and initialize its project-specific documents.
