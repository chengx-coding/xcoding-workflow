# Installation

**Language:** **English** | [简体中文](../zh-CN/getting-started/installation.md)

XC installation has two phases with two different owners. First, verify an immutable release and install the `xcoding` command line with `uv`. Second, let the installed CLI install the XC Skills and agent definitions for a user home or an explicit consumer project. The running CLI never installs its own first copy. `xcoding install`, `xcoding upgrade`, and `xcoding uninstall` are thin lifecycle entry points over the same setup transaction, manifest, recovery, and rollback rules as `xcoding setup`; they add entry points and reporting, not a second installer or a second state model.

## Prerequisites

- Windows x86_64. This is the formally supported platform; the [release matrix](#release-and-support-matrix) below is the authoritative support boundary.
- CPython 3.12 or newer, with CPython 3.12.13 as the formal verification baseline.
- `uv` on `PATH` for the isolated tool installation.
- At least one supported Agent host if you will use the workflow: Codex, OpenCode, Claude Code, or Trae.
- Git, with a configured identity if you want XC to save automatic workshop checkpoints.

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

## Two-phase bootstrap

The two phases have different owners and different evidence:

| Phase | Owner | Command | Result |
| --- | --- | --- | --- |
| 1. CLI | Release verification and `uv` | `uv tool install <verified wheel>` | The `xcoding` command on `PATH` |
| 2. Payload | The installed `xcoding` command | `xcoding install ...` | XC Skills, agent definitions, and the setup manifest |

The CLI phase runs before any XC command exists. The running CLI does not, and cannot, install its own first copy. The payload phase reads its desired files from the installed wheel's Bundle; it does not copy from a source checkout and it does not replace the CLI.

The boundary matters on Windows. The CLI can write a user home or a project payload, but replacing or removing the CLI itself is an external `uv` operation. `xcoding upgrade --wheel` starts that operation as a `uv` subprocess and reports an explicit failure when Windows refuses to replace a running program. `xcoding uninstall --all` reports the same external-step boundary rather than claiming that the running process removed itself.

## Obtain and verify the tool

Download the wheel, `SHA256SUMS`, `provenance.json`, `integrity-manifest.json`, `release-notes.en.md`, and `release-notes.zh-CN.md` from the same immutable GitHub Release. Before installation, verify that the wheel name, size, digest, distribution version, project commit, and Bundle digest match those release files. Candidate-specific hashes belong to the release assets and are intentionally not copied into these project documents.

Install the verified local wheel:

```console
uv tool install /absolute/path/to/xcoding_workflow-0.1.0-py3-none-any.whl
xcoding version --json
xcoding doctor --json
```

Builds containing the new shortcut also support `xcoding --version`; existing installations can keep using `xcoding version --json` until upgraded to a build containing that change. Reinstalling the same historical wheel does not add the capability.

This phase creates the CLI only. It does not install a Skill or agent definition, and no setup manifest exists yet. The payload phase below installs them from the same wheel.

The installation creates `xcoding`; there is no `xc` alias. XC does not distribute `install.ps1`, `install.sh`, remote-script pipe commands, or compatibility wrappers. Do not install a similarly named package from PyPI.

## Install the payload

`xcoding install` installs or reconciles the payload for one scope. It takes the following options:

```text
xcoding install [--scope user|project] [--project-root PATH] [--host HOST ...] [--dry-run] [--adopt-legacy] --json
```

`--scope` defaults to `user`. User scope resolves the home directory and accepts no `--project-root`; project scope requires an explicit `--project-root`. `--host` can be repeated. Omitting it selects the fixed default set of all four supported hosts: `claude-code`, `codex`, `opencode`, and `trae`. `--dry-run` is zero-write, and `--adopt-legacy` is the explicit user-scope legacy migration described below.

### User scope (default)

```console
xcoding install --json
```

User scope writes the payload under the home directory and records it in `<home>/.agents/.xcoding-setup/manifest.json`. This is the same manifest schema as a project setup; only the root differs. Manifest paths are relative to the home directory.

Host identifiers and fixed targets are the same for every root:

| Host ID | Subagent definitions | XC Skills |
| --- | --- | --- |
| `codex` | `.codex/agents` | `.agents/skills` |
| `opencode` | `.opencode/agents` | `.agents/skills` |
| `claude-code` | `.claude/agents` | `.claude/skills` |
| `trae` | `.trae/agents` | `.agents/skills` |

`.agents/skills` is shared by `codex`, `opencode`, and `trae`. The planner resolves each destination to its absolute path and writes that shared tree once, with one owner record per file; three selected hosts do not produce three copies. A default user install therefore also creates `.opencode/agents` when it does not already exist. Narrow the host set with `--host` if that is not wanted:

```console
xcoding install --host claude-code --host codex --json
```

The host set is complete desired state, not an incremental add list. Repeating a host is harmless. On a later successful install, adding a host installs its mapping; omitting a previously selected host removes only unchanged paths owned solely by that host. Shared Skills remain while any selected host owns them. Unowned files are never changed.

Inspect the exact plan without writing:

```console
xcoding install --dry-run --json
```

The dry run reports create, replace, remove, and unchanged operations plus the adoption plan, and always returns `writes_performed: false`. The reported plan is the real write plan, not a separate estimate.

### Legacy adoption (user scope only)

The 0.3.6 development installers recorded ownership in two legacy manifests: `<home>/.agents/.xc-skill-install-manifest.json` and `<home>/.claude/.xc-skill-install-manifest.json`. `--adopt-legacy` migrates them explicitly:

```console
xcoding install --scope user --adopt-legacy --json
```

Adoption is explicit; it does not happen on a plain `install` or `upgrade`. It is available only for user scope, and a project-scope request is rejected with `adopt_legacy_requires_user_scope`. The step verifies each legacy record against the file's current SHA-256 and claims only bytes that match the recorded hash. Desired files whose current bytes already equal the installed Bundle are also claimed, so an already-current copy does not become a conflict. A verified file that the new Bundle no longer distributes becomes a removal, which is how an old package such as `xc-change-report` is dropped. Drifted, missing, non-regular, unreadable, and host-not-selected records are preserved and reported instead of being overwritten or deleted; unknown content that neither manifest mentions is outside the transaction and is not touched, except generated `__pycache__`/`*.pyc`/`*.pyo` caches inside a retired package directory, which the cleanup removes and reports.

After a committed transaction, package directories that the legacy `expected_packages` records but the new Bundle no longer distributes are cleaned: generated `__pycache__` content and `*.pyc`/`*.pyo` files are removed, and directories that become empty are pruned. A non-cache file that the legacy manifests did not record is preserved and reported in the `adoption.cleanup` summary with reason `unrecorded`, and its package directory is kept. The same summary reports the retired package names, removed cache paths and counts, removed directories, preserved unrecorded paths, and any best-effort cleanup error; a cleanup warning never turns the committed transaction into a failure.

After a committed transaction, a legacy manifest is archived outside the setup state at `<home>/.agents/.xcoding-setup-legacy-<generation>/agents/` or `.../claude/` only when every one of its records was in scope and claimed. A manifest with any preserved record (host not selected, drifted, missing, non-regular, or unreadable) stays in place because it is still the only ownership record for those bytes; the result reports `archived: false` with the reason, and a later all-host `--adopt-legacy` can still read it. There is no `--force` for adoption, and a legacy record whose recorded hash disagrees with the current file is never claimed or removed.

### Configure Agent hosts in a project

`xcoding install --scope project --project-root /absolute/path/to/project --json` is a thin alias over the project-level setup engine. It requires an explicit existing project root, writes the project manifest at `<project>/.agents/.xcoding-setup/manifest.json`, and keeps `xcoding setup`'s transaction, manifest schema, recovery, and rollback behavior. It selects hosts the same way as user scope: all four by default, narrowed by `--host`.

You can also keep using `xcoding setup` directly. It requires an explicit project root and at least one explicit host; repeat `--host` for every host that should remain installed:

```console
xcoding setup --project-root /absolute/path/to/project --host codex --host opencode --host claude-code --host trae --json
```

Each selected host also receives its versioned `xc-delegation` capability statement as package-owned setup state. Setup validates that statement against the Bundle and reports its adapter version and security mode. The current Claude Code, Codex, OpenCode, and Trae statements are `adapter_version=unverified` and `mode=validated-only`; network and secret grants are unsupported. These statements prove deterministic preparation compatibility, not host execution isolation.

`xcoding setup` never infers the project from the current directory and does not detect hosts interactively: the project root and at least one host are explicit. `xcoding install` also has no interactive host detection; omitting `--host` uses the fixed four-host default set, and `--host` narrows it explicitly. Legacy adoption is the explicit, user-scope-only `--adopt-legacy` step. There is no force option for adoption or for overwriting a drifted managed file; `upgrade --force` only reinstalls an equal-version wheel.

The workshop repository topology is chosen during the workshop-setup step (default: independent workspace `independent-link`), not by `xcoding setup` or `xcoding install`.

## Inspect before writing

Add `--dry-run` to execute Bundle validation, root and path safety checks, conflict detection, ownership planning, and lock acquisition without changing the target:

```console
xcoding install --scope user --dry-run --json
xcoding setup --project-root /absolute/path/to/project --host codex --host trae --dry-run --json
```

The dry run reports create, replace, remove, and unchanged operations and always returns `writes_performed: false`. Setup and install fail closed before mutation when the Bundle is invalid, the root or lock cannot be proven, a target crosses a link or reparse point, an unmanaged target conflicts, a managed file has drifted, or unexpected setup state exists. Resolve the reported ownership or path issue; do not overwrite it manually and retry blindly.

## Upgrade

`xcoding upgrade` reconciles the payload to the installed CLI, and optionally replaces the CLI first. As with `install`, `--scope` defaults to `user`:

```text
xcoding upgrade [--scope user|project] [--project-root PATH] [--host HOST ...] [--wheel PATH] [--force] [--adopt-legacy] [--dry-run] --json
```

Without `--wheel`, it reconciles the payload to the running CLI and reports `up-to-date` when every operation is unchanged, `reconciled` when it changed something, or `dry-run` for a dry run. It does not replace the CLI.

With `--wheel`, it first reads the `Name` and `Version` fields from the wheel's `.dist-info/METADATA` and validates that the distribution is `xcoding-workflow` and the requested version is usable. When the wheel version equals the running CLI version and `--force` is absent, the CLI step is skipped, reported as `skipped-equal-version`, and only the payload is reconciled. Otherwise it runs `uv tool install --force <wheel>`, then invokes the newly installed CLI with `xcoding install --scope ... --json` for the payload phase. Before reporting `status: "upgraded"`, it requires the payload envelope's `version` to equal the target version and, when the target differs from the running version, its Bundle hash to differ from the running Bundle (or match the Bundle the wheel carries). A payload that ran an older CLI fails with `cli_upgraded_payload_failed`; the result reports the CLI step and the payload result together.

`--force` is a wheel-reinstall flag: with a wheel whose version already equals the running CLI, it forces the CLI step instead of skipping it. It is not an adoption force and never overwrites a drifted managed file. Legacy adoption is always explicit: both `install` and `upgrade` adopt only when `--adopt-legacy` is passed, and a user-scope `upgrade` without the flag never adopts or archives the legacy records (a legacy payload whose unowned bytes collide with the new Bundle fails closed with `unmanaged_conflict` instead). Project scope rejects `--adopt-legacy`.

The CLI replacement can fail on Windows while the current process is running. Failures are structured and never reported as success:

| Code | Meaning | Payload writes |
| --- | --- | --- |
| `cli_upgrade_failed` | `uv` could not install the requested wheel. | None; the payload phase does not start. |
| `cli_upgrade_requires_external_step` | `uv` was blocked by a running or locked program, typically a Windows file-in-use condition. Close every `xcoding` process and run the reported `uv tool install --force` command again. | None; the payload phase does not start. |
| `cli_upgraded_payload_failed` | The CLI was replaced, but the payload install failed, returned nonzero, returned an unusable envelope, or did not run the target CLI version. The installation is not complete; resolve the reported payload error and rerun `xcoding upgrade` or `xcoding install`. | The payload phase started and failed; this is a nonzero result. |

`wheel_invalid` (a missing, unreadable, non-wheel, version-less, or foreign-distribution path) and `uv_unavailable` (no `uv` on `PATH`) are also reported before any payload write. With a different wheel and `--dry-run`, the result reports the `uv tool install --force` command as `would-run` and defers the payload plan as `deferred-until-cli-upgrade`, because the target Bundle exists only after the new CLI is installed; nothing is written.

```console
xcoding upgrade --json
xcoding upgrade --wheel /absolute/path/to/<verified-wheel>.whl --json
xcoding upgrade --scope project --project-root /absolute/path/to/project --json
```

## Uninstall

`xcoding uninstall` removes the payload for one scope. As with `install`, `--scope` defaults to `user`:

```text
xcoding uninstall [--scope user|project] [--project-root PATH] [--keep-state] [--all] [--dry-run] --json
```

Payload removal is hash-guarded. The command reads the setup manifest and removes a file only when the path is manifest-owned and its current SHA-256 still matches the recorded hash; the hash is re-checked immediately before each delete, so a file that changes after planning aborts the removal instead of deleting new bytes. Modified owned files, non-regular files, user-authored Skills such as `lark-*`, project-only Skills, and unknown content are preserved and reported. Empty managed package parent directories are pruned bottom-up; pruning stops at the host target root, and the shared `.agents` convention directory is never removed.

After a real payload removal, the setup state directory is archived as `<root>/.agents/.xcoding-setup-uninstalled-<generation>/` rather than deleted. `--keep-state` keeps the full archive, including the manifest and the `backup/` and `staging/` data needed for recovery. Without `--keep-state`, the default writes `receipt.json` inside the archive and drops `backup/` and `staging/`, leaving an audit receipt instead of a full backup. A second uninstall on the same root is a no-op that reports `installed: false` and performs no write.

A root with no setup manifest but a 0.3.6 legacy manifest is not a no-op. Removing nothing while XC-owned legacy bytes remain would be a false success, so `uninstall` fails with `legacy_payload_present` and exit code 4, reports the legacy summary, and names the next action `xcoding install --scope user --adopt-legacy, then xcoding uninstall`. A clean root with neither a setup manifest nor a legacy manifest still reports `installed: false` and writes nothing.

Without `--all`, the command removes only the payload and reports the remaining CLI step explicitly:

```console
xcoding uninstall --json
```

The result contains `cli_removal: "external-required"` and the exact command to run externally: `uv tool uninstall xcoding-workflow`. The command exits 0 because the requested payload operation completed and the CLI step was not requested.

With `--all`, it also attempts that `uv tool uninstall` step. A successful removal reports `cli_removal: "removed"`. A failure reports a nonzero `cli_removal_failed` result that still contains the complete payload result under `error.details.payload`; `error.details.cli_removal` remains `external-required` with the exact command, return code, and bounded output. `--all --dry-run` reports `cli_removal: "dry-run"` and spawns no process.

A running CLI cannot delete itself on Windows. If `uv` cannot remove the tool because the process or a shell still holds it, close every `xcoding` process and run `uv tool uninstall xcoding-workflow` from a new shell. The command never reports a failed CLI removal as full success.

```console
xcoding uninstall --scope user --keep-state --json
xcoding uninstall --scope project --project-root /absolute/path/to/project --all --json
```

## Readiness check

`xcoding doctor --json` reports the running CLI: the `python`, `path`, `git`, `tk`, `bundle`, and `delegation-adapters` checks. Adding `--target-root` also runs the `target` check and the read-only `payload` check for that root:

```console
xcoding doctor --target-root <home> --json
xcoding doctor --target-root /absolute/path/to/project --json
```

The payload check reads `<target-root>/.agents/.xcoding-setup/manifest.json`; only when that setup manifest is absent does it additionally read the two legacy `.xc-skill-install-manifest.json` files under `.agents/` and `.claude/`. It writes nothing, takes no lock, and claims nothing. A fully clean target has neither kind of manifest: the check is `not-installed`, is not required, and adds the `payload-not-installed` warning instead of failing. A target with no setup manifest but at least one legacy manifest is a 0.3.6 layout rather than a clean machine: the check is `legacy`, is required, fails, sets `ready: false`, and exits with code 4. It reports the legacy manifest paths, source revisions, package and file counts, per-manifest errors, a `legacy-install-detected` problem, and a `next_action` naming `xcoding install --scope user --adopt-legacy`. If the setup manifest exists, the check compares its version and Bundle hash with the running CLI, verifies every manifest-owned file, and classifies the payload as `current`, `stale`, `missing`, `modified`, or `invalid`; any installed payload that is not `current` also fails the required check, sets `ready: false`, and exits with code 4 and error code `readiness-failed`.

The payload details report the generation, host set, manifest and running versions, manifest and running Bundle hashes, counts, the `kinds` split between Skills and agent definitions, the ownership counts with the preserved-files note, and a `problems` list with the path, expected and actual hashes, owners, and per-file status. Files outside the manifest are reported as preserved, not evaluated. A legacy-only target reports the legacy summary instead of a generation and per-file counts. Run the command once against `<home>` for the user-level payload and once against a project root for the project-level payload; the CLI checks are identical in both runs.

## Managed upgrades and state

Every lifecycle command uses one transaction engine, one manifest schema, and one state directory. `xcoding install` and `xcoding upgrade` write through the same staged transaction as `xcoding setup`; `xcoding uninstall` archives the same state. No command creates a second manifest or a second source of truth.

The setup manifest records exactly:

- `schema_version` — the manifest schema version.
- `distribution` — `xcoding-workflow`.
- `version` — the installed Bundle version.
- `bundle_manifest_sha256` — the Bundle identity.
- `generation` — the successful transaction's 32-hex generation.
- `previous_generation` — the generation that rollback restores, when one exists.
- `hosts` — the complete selected host set, in canonical order.
- `files` — per-file records with the path relative to the root, `mode`, SHA-256, and shared owner list.

Scope is not a manifest field; the root determines it. The user manifest is at `<home>/.agents/.xcoding-setup/manifest.json`, and the project manifest is at `<project>/.agents/.xcoding-setup/manifest.json`.

Transaction state lives in the same `.agents/.xcoding-setup/` directory under the target root:

- `manifest.json` records the successful generation.
- `journal.json` records an interrupted transaction and is present only when recovery may be required.
- `staging/` holds package-owned transaction data for the in-progress generation.
- `backup/<generation>/` holds the previous generation's bytes needed for rollback.

An ordinary setup performs first installation and managed upgrade through one staged transaction. It verifies all desired bytes before touching targets, records intent durably, uses atomic replacement, and publishes the ownership manifest only after target operations succeed. An interrupted transaction leaves durable state for explicit recovery rather than pretending that partial work succeeded.

Setup and install remove only paths that the manifest owns and whose current identity still matches the recorded managed bytes. Unmanaged files and drift remain user-owned conflicts. Uninstall preserves a modified owned file and reports it rather than deleting it.

Two history archives sit beside the live state directory and are not part of the current state model:

- `.agents/.xcoding-setup-legacy-<generation>/` holds the archived legacy manifests after an explicit adoption. It is created outside `.agents/.xcoding-setup/` so idle-state validation remains unchanged.
- `.agents/.xcoding-setup-uninstalled-<generation>/` holds the archived state directory after an uninstall, with either a full backup (`--keep-state`) or a receipt and no backup/staging.

Install is idempotent: an immediate repeat reports only `unchanged` operations. Uninstall is idempotent: a repeat reports `installed: false` and writes nothing. Both scopes take the shared setup lock for the target root; a concurrent operation is refused with `setup_locked` and exit 4 instead of interleaving writes.

## Recovery and rollback

For a project root, the setup recovery and rollback rules remain the supported controls. If setup or install reports `recovery_required`, close the interrupted journal explicitly:

```console
xcoding setup --project-root /absolute/path/to/project --recover --json
```

Recovery inspects the durable journal and either completes a transaction whose manifest was already committed or restores the prior generation. It is idempotent for the same recoverable state and does not accept `--host` or `--dry-run`.

To restore the immediately preceding successful generation, use:

```console
xcoding setup --project-root /absolute/path/to/project --rollback --json
```

Rollback also rejects `--host` and `--dry-run`. It is available only when a valid previous generation exists and no open journal requires recovery. Neither operation deletes unowned files or overwrites drifted managed bytes. A lock, identity, journal, backup, or rollback failure remains a machine-readable error that requires diagnosis; it is never converted into a best-effort destructive cleanup.

User scope does not expose a separate rollback command. A real uninstall archives the state under `.agents/.xcoding-setup-uninstalled-<generation>/` for inspection and manual restore, and `--keep-state` keeps the full backup. Archived legacy manifests from an adoption remain under `.agents/.xcoding-setup-legacy-<generation>/`; a legacy manifest that still owns preserved bytes stays in its host root. To recover a user payload from scratch, reinstall the verified wheel and run `xcoding install --scope user` again.

Capability statements participate in the same transaction, recovery, and rollback rules as the Agent and Skill files. Rolling back to a generation that predates those statements is reported explicitly as `legacy-prompt` compatibility; it does not masquerade as `prepared-profile` support. `xcoding doctor --json` treats delegation adapters as a required check, reports the installed mode, and warns for every non-enforced statement. Skill-local profiles are current-only and must be regenerated without a root `schema_version`; old profile documents are rejected rather than silently migrated.

## Migrate from the 0.3.6 development-installer layout

A user home prepared by the 0.3.6 development installers has `.agents/skills` and `.claude/skills` trees plus the two legacy `.xc-skill-install-manifest.json` files, but no `.agents/.xcoding-setup/manifest.json`. The supported migration is explicit and preserves every file that cannot be verified. Run these steps in order:

```console
uv tool install /absolute/path/to/xcoding_workflow-0.4.19-py3-none-any.whl
xcoding install --scope user --adopt-legacy --json
xcoding doctor --target-root <home> --json
```

1. Install the target wheel with `uv`, as in the CLI phase above.
2. Run the explicit user-scope adoption. Review the plan first with `--dry-run` if you want to see the claims, removals, and preserved files before writing. Verified old files are claimed, packages that the new Bundle no longer distributes are removed only when their hashes match, and drifted or unknown files are preserved and reported.
3. Run the read-only payload check against the home root. It must report the payload as `current`. Before adoption it reports `legacy` and fails the required check, because the two 0.3.6 manifests are still present and no setup manifest exists yet; that failure is the signal to run the adoption step above.

A successful migration ends with 25 `xc-*` Skill packages, no `xc-change-report` package, `xc-visual-design` present, and the current agent definitions in the selected host roots, provided no unrecorded non-cache file remains inside a retired package directory. After the transaction commits, a package that the legacy `expected_packages` records but the new Bundle no longer distributes is cleaned: generated `__pycache__` content and `*.pyc`/`*.pyo` files are removed, and empty directories are pruned. A non-cache file that the legacy manifests did not record is preserved and reported in the `adoption.cleanup` summary with reason `unrecorded`, and it keeps its package directory; the 25-package, no-`xc-change-report` end state therefore holds when no such file remains. Existing non-XC Skills such as `lark-*` and `x-public-reader` are untouched. The result reports preserved legacy records under `adoption.preserved` and retired-package residue under `adoption.cleanup`. A legacy manifest whose every record was claimed is moved into `.agents/.xcoding-setup-legacy-<generation>/` so the old tree is no longer authoritative, while a manifest that still has a preserved record stays in place and is reported; a later all-host adoption can finish it after the drift is resolved. A later uninstall archives the new state instead of touching those archives.

If the adoption reports drift, do not delete the file to force progress. Restore the recorded bytes when the old copy is still wanted, or move the customized copy out of the managed path, then rerun the same sequence. There is no force option that overrides the hash check.

`xcoding install`, `xcoding upgrade`, and `xcoding uninstall` are the supported consumer path for the CLI and its payload. The checkout scripts `install_skills.py`, `skills/xc-workflow-evolution/scripts/install_xc_skills.py`, and `build_agents.py` remain development-only; they are not the consumer installation path and do not create the setup manifest described here.

## Skill installation paths

`xcoding install` is the supported installation path for consumers, at user scope by default and at project scope with `--scope project --project-root`. It installs the selected hosts' XC Skills and subagent definitions from the installed wheel and owns them through the setup transaction, manifest, recovery, and rollback rules described above. `xcoding upgrade` and `xcoding uninstall` operate on the same owned payload.

The source-tree installer [`install_skills.py`](../../install_skills.py) is a **development path** for this checkout only. It requires an explicit `--target-skills`, copies the canonical packages from the checkout it lives in, and is not part of the release contract. Use it to refresh a development target from this source tree, not to install a supported consumer project.

That development installer replaces only the `xc-*` packages the previous install manifest owns, or that the canonical source set is about to install. An `xc-*` directory the manifest does not own and the canonical source does not provide survives a plain install and is reported as preserved; `--force` replaces it instead, and that flag belongs to the development path only. It deletes and reinstalls every package it replaces, so it does not compare their bytes with the previous manifest; the fail-closed drift rule belongs to the `xcoding` setup transaction used by `install` and `setup`.

The workflow-evolution development installer `skills/xc-workflow-evolution/scripts/install_xc_skills.py` and the checkout-local Skill sync script `build_agents.py` are maintenance tools for developing this repository. They do not install XC into a consumer user home or project, and the public installation path does not depend on them.

## Exit codes and JSON output

Every machine-readable `xcoding` command requires an explicit `--json`; the only standalone exception is `xcoding --version`, which prints `xcoding <version>` on success. A missing `--json` exits with code 2 and the `json-required` error, before any side effect. Every command that accepts `--json` emits exactly one JSON envelope: on success `{schema_version, ok: true, command, result}`; on failure `{schema_version, ok: false, command, error: {code, message, details}}`.

| Exit code | Meaning |
| --- | --- |
| 0 | Success. For `uninstall` without `--all`, the payload phase succeeded and the CLI step is reported as `external-required`. |
| 2 | Input error, including `invalid_arguments` and `json-required`. No write occurs. |
| 3 | Bundle or installed-version validation failure. |
| 4 | Readiness or lifecycle failure: `readiness-failed`, `managed_content_changed`, `unmanaged_conflict`, `legacy_manifest_conflict`, `legacy_manifest_invalid`, `legacy_payload_present`, `path_identity_changed`, `uninstall_archive_conflict`, `setup_locked`, `recovery_required`, `journal_invalid`, `project_root_required`, `project_root_not_allowed`, `host_unknown`, `adopt_legacy_requires_user_scope`, `wheel_invalid`, `uv_unavailable`, `cli_upgrade_failed`, `cli_upgrade_requires_external_step`, `cli_upgraded_payload_failed`, and `cli_removal_failed`. |
| 5 | Unclassified internal failure. |

The error code is stable across commands. A consumer should branch on `error.code` and read `error.details` rather than parse messages. For `uninstall --all` failure, `error.details.payload` contains the complete payload result, so a failed CLI removal does not discard the payload evidence.

## Prepare a Skill-local worker

An owning `xc-*` Skill may define a private profile at `assets/workers/<profile-id>/profile.json` and delegate it through the installed `xc-delegated-agent`. The public [`xc-delegation` contract](../../skills/xc-delegation/SKILL.md) defines the profile, policy, overlay, adapter, and envelope inputs. The supported command surface is:

```console
xcoding delegate validate-profile --skill-root /absolute/path/to/skill --profile-id read-only-evidence --json
xcoding delegate resolve-profile --skill-root /absolute/path/to/skill --profile-id read-only-evidence --json
xcoding delegate prepare --skill-root /absolute/path/to/skill --profile-id read-only-evidence --node-packet-json node.json --node-profile-ref-json profile-ref.json --project-policy-json project-policy.json --adapter-id codex --caller-constraints-json caller.json --out envelope.json --json
```

The node packet and profile reference come from the runtime's read-only `assignment-packet` operation for the exact running subagent attempt. Only a successful `prepare` result may set `dispatch_authoritative=true`. Validation, resolution, diagnostic compilation, and the read-only `scan-legacy` operation do not authorize dispatch. A malformed, stale, denied, expired, or unsupported v1 request stops; it never silently retries as `legacy-prompt`.

Private profiles stay with their owning Skill. Use a persistent canonical Agent instead when a role is shared across Skills, directly selectable by users, or needs a distinct persistent model or permission identity.

## Migrate a renamed agent definition

A canonical agent definition is installed under one filename per host, and that filename is part of the managed state of every project that installed it. The agent definition formerly installed as `delegate-agent` is now `xc-delegated-agent`, so a project that installed the earlier name sees one removal paired with one creation per selected host. The host roots are unchanged, and only the installed filename changes:

| Host ID | Installed before | Installed after |
| --- | --- | --- |
| `claude-code` | `.claude/agents/delegate-agent.md` | `.claude/agents/xc-delegated-agent.md` |
| `codex` | `.codex/agents/delegate-agent.toml` | `.codex/agents/xc-delegated-agent.toml` |
| `opencode` | `.opencode/agents/delegate-agent.md` | `.opencode/agents/xc-delegated-agent.md` |
| `trae` | `.trae/agents/delegate-agent.md` | `.trae/agents/xc-delegated-agent.md` |

The change happens on the next successful `xcoding setup` or `xcoding install --scope project` after the upgrade to the release that carries the new name. Setup deletes the old-named file and installs the new-named file inside the same transaction; shared Skill files are reported `unchanged`. The transaction is not name-aware. It is the ordinary desired-state reconciliation described above, applied to a Bundle whose resource paths changed.

Run the dry run first:

```console
xcoding setup --project-root /absolute/path/to/project --host codex --host opencode --host claude-code --host trae --dry-run --json
```

It reports the removal and the creation as paired operations, returns `writes_performed: false`, and leaves every file untouched. `--json` is not optional here: every machine-readable `xcoding` command requires an explicit `--json`, and omitting it exits with code 2 and the `json-required` error instead of returning a plan. Because the dry run executes the complete preflight, it also reports the blocking conditions below before anything is written.

Setup removes a previously installed file only when all four conditions hold at once: the path is recorded in the ownership manifest, the path is absent from the desired set computed from the currently installed Bundle and the selected host set, the file exists on disk, and its SHA-256 equals the manifest record. Nothing else in the transaction can delete a project file.

A migrating consumer must therefore leave the old-named agent file byte-identical until the upgrade run, and must not delete, move, or rename it: a hand-deleted manifest-owned file blocks the migration rather than helping it. The consumer must also not pre-create anything at the new path, even an exact copy of the packaged definition.

Every condition below fails closed and performs no write. Three of the five conditions name the offending path in `error.details.path`: `unmanaged_conflict` and both `managed_content_changed` variants. `recovery_required` and `journal_invalid` report no path: their error envelope carries an empty `details` object, so a consumer that parses `error.details.path` must handle its absence for those two. The code is the `error.code` value in the machine-readable error envelope, and the process exit code is 4:

- `unmanaged_conflict` — a file already exists at the new path but is not manifest-owned. Project-scope setup never adopts an unmanaged file; the only adoption path is the explicit user-scope `--adopt-legacy` legacy migration.
- `managed_content_changed` — a manifest-owned file's bytes no longer equal the recorded bytes. A local edit to the old-named agent file blocks the migration.
- `managed_content_changed` — a manifest-owned file is missing from disk. A hand-deleted old-named agent file blocks the migration.
- `recovery_required` — an interrupted transaction's journal is present. Ordinary setup refuses and demands `--recover`.
- `journal_invalid` — `--recover` runs under a different Bundle than the one that opened the interrupted transaction, reported as `recovery package Bundle differs from the interrupted transaction`. The consumer cannot proceed until the original wheel is reinstalled.

Because the wheel is what changed, close any interrupted setup with the wheel that is installed now, before the upgrade:

```console
xcoding setup --project-root /absolute/path/to/project --recover --json
```

If the wheel is replaced first, `--recover` fails with `journal_invalid` and ordinary setup fails with `recovery_required`, and neither advances until the original wheel is back.

`xcoding install` reconciles the payload when the installed bytes still match the manifest, and a real adoption can reclaim verified legacy bytes, but no force or adopt option overwrites a drifted managed file. If a managed file was customized, the only supported remedy is restoring that file's installed bytes; a customization worth keeping must be moved out of the managed path first. `--adopt-legacy` is a user-scope legacy migration, not a project-scope override, and `upgrade --force` only controls the equal-version wheel reinstall.

After a successful migration, the old-named file is gone from each configured host root, the new-named file is present, and `.agents/.xcoding-setup/manifest.json` lists the new paths. The old name still remains in the current generation's rollback backup under `.agents/.xcoding-setup/backup/<generation>/`, and `xcoding setup --rollback --json` restores the immediately preceding generation, which puts the old name back. It accepts neither `--host` nor `--dry-run`, and it refuses while a journal requires recovery. Setup also leaves a vacated host directory in place. A check that searches the project for the old name must therefore say where that name remains legitimate. References the consumer wrote by the host-visible emitted name, or by filename on a host without one, are outside what the repository can detect; the consumer updates them.

### Version-disposition basis for this rename

Historical decision: the user judged the earlier rename to be compatible maintenance that did not break a documented public contract, and deferred the numerical bump to a later release, leaving the version at `0.1.0` at that time. The rationale was that tracked contracts did not explicitly make installed agent filenames or host-visible handles contract terms; the tension with the maintenance-policy interpretation remains evidence for reconsideration. This decision is neither approval for future bumps nor a standing exception; subsequent iterations and cumulative unpublished changes are assessed under the [version policy](../development/versioning.md).

## Release and maintenance policy

GitHub Releases are the only release channel for `0.1.0`; PyPI, private indexes, remote install scripts, and alternate registries are outside this contract. A release must bind one immutable tag, project commit, wheel digest, Bundle digest, exact asset set, support-matrix evidence, and bilingual release notes. Publication occurs only after the candidate gates pass and a user explicitly approves release; these installation documents do not authorize publication.

Maintenance is best effort for the latest `0.1.x` patch only. There is no service-level agreement and no guaranteed backport to older patches. A change that breaks a documented public contract belongs in `0.2.0` or another later minor version rather than a `0.1.x` patch. If a new support line replaces `0.1.x` or maintenance ends, the release notes must announce the migration or end-of-support boundary and retain rollback guidance in both languages.

Continue with the [quick start](quick-start.md) to create the independent workshop and initialize its project-specific documents.
