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
xcoding setup --project-root /absolute/path/to/project --host codex --host opencode --host claude-code --host trae --json
```

Host identifiers and project-relative targets are fixed:

| Host ID | Subagent definitions | XC Skills |
| --- | --- | --- |
| `codex` | `.codex/agents` | `.agents/skills` |
| `opencode` | `.opencode/agents` | `.agents/skills` |
| `claude-code` | `.claude/agents` | `.claude/skills` |
| `trae` | `.trae/agents` | `.agents/skills` |

Each selected host also receives its versioned `xc-delegation` capability statement as package-owned setup state. Setup validates that statement against the Bundle and reports its adapter version and security mode. The current Claude Code, Codex, OpenCode, and Trae statements are `adapter_version=unverified` and `mode=validated-only`; network and secret grants are unsupported. These statements prove deterministic preparation compatibility, not host sandbox enforcement.

The host set is complete desired state, not an incremental add list. Repeating a host is harmless. On a later successful setup, adding a host installs its mapping; omitting a previously selected host removes only unchanged paths owned solely by that host. Shared Skills remain while any selected host owns them.

Setup never infers the project from the current directory, detects hosts automatically, adopts unmanaged files, or accepts a force option.

The workshop repository topology is chosen during the workshop-setup step (default: independent workspace `independent-link`), not by `xcoding setup`.

## Prepare a Skill-local worker

An owning `xc-*` Skill may define a private profile at `assets/workers/<profile-id>/profile.json` and delegate it through the installed `xc-delegated-agent`. The public [`xc-delegation` contract](../../skills/xc-delegation/SKILL.md) defines the profile, policy, overlay, adapter, and envelope inputs. The supported command surface is:

```console
xcoding delegate validate-profile --skill-root /absolute/path/to/skill --profile-id read-only-evidence --json
xcoding delegate resolve-profile --skill-root /absolute/path/to/skill --profile-id read-only-evidence --json
xcoding delegate prepare --skill-root /absolute/path/to/skill --profile-id read-only-evidence --node-packet-json node.json --node-profile-ref-json profile-ref.json --project-policy-json project-policy.json --adapter-id codex --caller-constraints-json caller.json --out envelope.json --json
```

The node packet and profile reference come from the runtime's read-only `assignment-packet` operation for the exact running subagent attempt. Only a successful `prepare` result may set `dispatch_authoritative=true`. Validation, resolution, diagnostic compilation, and the read-only `scan-legacy` operation do not authorize dispatch. A malformed, stale, denied, expired, or unsupported v1 request stops; it never silently retries as `legacy-prompt`.

Private profiles stay with their owning Skill. Use a persistent canonical Agent instead when a role is shared across Skills, directly selectable by users, or needs a distinct persistent model or permission identity.

## Inspect before writing

Add `--dry-run` to execute Bundle validation, project-root and path safety checks, conflict detection, ownership planning, and lock acquisition without changing the project:

```console
xcoding setup --project-root /absolute/path/to/project --host codex --host trae --dry-run --json
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
xcoding setup --project-root /absolute/path/to/project --recover --json
```

Recovery inspects the durable journal and either completes a transaction whose manifest was already committed or restores the prior generation. It is idempotent for the same recoverable state and does not accept `--host` or `--dry-run`.

To restore the immediately preceding successful generation, use:

```console
xcoding setup --project-root /absolute/path/to/project --rollback --json
```

Rollback also rejects `--host` and `--dry-run`. It is available only when a valid previous generation exists and no open journal requires recovery. Neither operation deletes unowned files or overwrites drifted managed bytes. A lock, identity, journal, backup, or rollback failure remains a machine-readable error that requires diagnosis; it is never converted into a best-effort destructive cleanup.

Capability statements participate in the same transaction, recovery, and rollback rules as the Agent and Skill files. Rolling back to a generation that predates those statements is reported explicitly as `legacy-prompt` compatibility; it does not masquerade as profile-v1 support. `xcoding doctor --json` treats delegation adapters as a required check, reports the installed mode, and warns for every non-enforced statement.

## Migrate a renamed agent definition

A canonical agent definition is installed under one filename per host, and that filename is part of the managed state of every project that installed it. The agent definition formerly installed as `delegate-agent` is now `xc-delegated-agent`, so a project that installed the earlier name sees one removal paired with one creation per selected host. The host roots are unchanged, and only the installed filename changes:

| Host ID | Installed before | Installed after |
| --- | --- | --- |
| `claude-code` | `.claude/agents/delegate-agent.md` | `.claude/agents/xc-delegated-agent.md` |
| `codex` | `.codex/agents/delegate-agent.toml` | `.codex/agents/xc-delegated-agent.toml` |
| `opencode` | `.opencode/agents/delegate-agent.md` | `.opencode/agents/xc-delegated-agent.md` |
| `trae` | `.trae/agents/delegate-agent.md` | `.trae/agents/xc-delegated-agent.md` |

The change happens on the next successful `xcoding setup` after the upgrade to the release that carries the new name. Setup deletes the old-named file and installs the new-named file inside the same transaction; shared Skill files are reported `unchanged`. The transaction is not name-aware. It is the ordinary desired-state reconciliation described above, applied to a Bundle whose resource paths changed.

Run the dry run first:

```console
xcoding setup --project-root /absolute/path/to/project --host codex --host opencode --host claude-code --host trae --dry-run --json
```

It reports the removal and the creation as paired operations, returns `writes_performed: false`, and leaves every file untouched. `--json` is not optional here: every machine-readable `xcoding` command requires an explicit `--json`, and omitting it exits with code 2 and the `json-required` error instead of returning a plan. Because the dry run executes the complete preflight, it also reports the blocking conditions below before anything is written.

Setup removes a previously installed file only when all four conditions hold at once: the path is recorded in the ownership manifest, the path is absent from the desired set computed from the currently installed Bundle and the selected host set, the file exists on disk, and its SHA-256 equals the manifest record. Nothing else in the transaction can delete a project file.

A migrating consumer must therefore leave the old-named agent file byte-identical until the upgrade run, and must not delete, move, or rename it: a hand-deleted manifest-owned file blocks the migration rather than helping it. The consumer must also not pre-create anything at the new path, even an exact copy of the packaged definition.

Every condition below fails closed and performs no write. Three of the five conditions name the offending path in `error.details.path`: `unmanaged_conflict` and both `managed_content_changed` variants. `recovery_required` and `journal_invalid` report no path: their error envelope carries an empty `details` object, so a consumer that parses `error.details.path` must handle its absence for those two. The code is the `error.code` value in the machine-readable error envelope, and the process exit code is 4:

- `unmanaged_conflict` — a file already exists at the new path but is not manifest-owned. Setup never adopts an unmanaged file.
- `managed_content_changed` — a manifest-owned file's bytes no longer equal the recorded bytes. A local edit to the old-named agent file blocks the migration.
- `managed_content_changed` — a manifest-owned file is missing from disk. A hand-deleted old-named agent file blocks the migration.
- `recovery_required` — an interrupted transaction's journal is present. Ordinary setup refuses and demands `--recover`.
- `journal_invalid` — `--recover` runs under a different Bundle than the one that opened the interrupted transaction, reported as `recovery package Bundle differs from the interrupted transaction`. The consumer cannot proceed until the original wheel is reinstalled.

Because the wheel is what changed, close any interrupted setup with the wheel that is installed now, before the upgrade:

```console
xcoding setup --project-root /absolute/path/to/project --recover --json
```

If the wheel is replaced first, `--recover` fails with `journal_invalid` and ordinary setup fails with `recovery_required`, and neither advances until the original wheel is back.

There is no repair command and no force or adopt option. If a managed file was customized, the only supported remedy is restoring that file's installed bytes; a customization worth keeping must be moved out of the managed path first.

After a successful migration, the old-named file is gone from each configured host root, the new-named file is present, and `.agents/.xcoding-setup/manifest.json` lists the new paths. The old name still remains in the current generation's rollback backup under `.agents/.xcoding-setup/backup/<generation>/`, and `xcoding setup --rollback --json` restores the immediately preceding generation, which puts the old name back. It accepts neither `--host` nor `--dry-run`, and it refuses while a journal requires recovery. Setup also leaves a vacated host directory in place. A check that searches the project for the old name must therefore say where that name remains legitimate. References the consumer wrote by the host-visible emitted name, or by filename on a host without one, are outside what the repository can detect; the consumer updates them.

### Version-disposition basis for this rename

The rename is not being treated as a change that breaks a documented public contract, so it is delivered as an ordinary `0.1.x` patch rather than being routed into `0.2.0` or another later minor version. This is a recorded user judgement, and it is in tension with the maintenance policy sentence above: no tracked statement in this repository makes an installed agent filename or a host-visible agent handle a contract term, and this page records only the host identifiers and their project-relative target roots. The tension is not resolved here. The version number and its carriers are unchanged: `pyproject.toml` stays at `0.1.0`, and any version bump is deferred to a later release.

## Release and maintenance policy

GitHub Releases are the only release channel for `0.1.0`; PyPI, private indexes, remote install scripts, and alternate registries are outside this contract. A release must bind one immutable tag, project commit, wheel digest, Bundle digest, exact asset set, support-matrix evidence, and bilingual release notes. Publication occurs only after the candidate gates pass and a user explicitly approves release; these installation documents do not authorize publication.

Maintenance is best effort for the latest `0.1.x` patch only. There is no service-level agreement and no guaranteed backport to older patches. A change that breaks a documented public contract belongs in `0.2.0` or another later minor version rather than a `0.1.x` patch. If a new support line replaces `0.1.x` or maintenance ends, the release notes must announce the migration or end-of-support boundary and retain rollback guidance in both languages.

Continue with the [quick start](quick-start.md) to create the independent workshop and initialize its project-specific documents.
