# Orchestration Services

**Language:** **English** | [Simplified Chinese (简体中文)](../../zh-CN/reference/skills/orchestration-services.md)

These services design, run, and visualize managed orchestration without taking ownership of domain work.

## `xc-orchestration-author`

[Canonical contract](../../../skills/xc-orchestration-author/SKILL.md)

- **Invoke when:** an approved workflow needs a new managed template or a prose flow must become runtime-controlled.
- **Purpose:** design and validate JSON flow specifications and build integrity-protected schema-version-1 templates.
- **Public entry:** `template_builder.py` commands `new-spec`, `validate-spec`, `build`, and `validate-template`.
- **Typical usage:** model phases, dependencies, gates, dynamic groups, and bounded loops; build the template and smoke-test `init -> next`.
- **Boundaries:** it does not execute runtime nodes; domain data uses metadata and artifacts rather than new runtime node types or large blackboard values.

## `xc-orchestration-runtime`

[Canonical contract](../../../skills/xc-orchestration-runtime/SKILL.md)

- **Invoke when:** a workflow needs scheduling, node transitions, controlled state updates, subtree embedding, integrity operations, snapshots, or persistence.
- **Purpose:** provide the domain-neutral control plane for managed runtime trees and transactional workshop checkpoints.
- **Public entry:** `orchestration.py` lifecycle commands such as `init`, `next`, `start`, `complete`, `fail`, and `block`, plus documented query and recovery commands.
- **Typical usage:** initialize a template, request ready work, start only an executable leaf, and terminate a running node with concise evidence and declared artifacts.
- **Boundaries:** managed XML is never read or edited directly; workers execute exactly one node, invalid integrity requires explicit repair, and successful trees remain sealed until an approved reopen.

## `xc-orchestration-viewer`

[Canonical contract](../../../skills/xc-orchestration-viewer/SKILL.md)

- **Invoke when:** a user asks to open, monitor, or visualize managed runtime progress.
- **Purpose:** provide a script-free facade over the runtime-owned, loopback-only, read-only viewer.
- **Public entry:** launch the runtime `viewer_server.py` with `--tree`; use `runtime_skill_dir` for a non-sibling installation and `--allow-root` only for additional permitted directories.
- **Typical usage:** start the detached local server, inspect snapshots in the browser, pan or zoom the graph, and download a complete SVG.
- **Boundaries:** it owns no parser, state machine, server, or frontend and exposes no mutation endpoint; selected trees and native-picker authorization remain narrowly scoped.
