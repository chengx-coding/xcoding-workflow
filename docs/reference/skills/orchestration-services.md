# Orchestration Services

**Language:** **English** | [简体中文](../../zh-CN/reference/skills/orchestration-services.md)

These services design, run, and visualize managed orchestration without taking ownership of domain work.

## `xc-orchestration-author`

[Canonical contract](../../../skills/xc-orchestration-author/SKILL.md)

- **Invoke when:** an approved workflow needs a new managed template or a prose flow must become runtime-controlled.
- **Purpose:** design and validate JSON flow specifications and build integrity-protected schema-version-1 templates.
- **Public entry:** `template_builder.py` commands `new-spec`, `validate-spec`, `build`, and `validate-template`.
- **Typical usage:** model phases, dependencies, gates, dynamic groups, bounded loops, and leaf-owned control metadata; validate the flow spec, build the generated template, validate it, and smoke-test `init -> next`.
- **Boundaries:** the JSON flow specification is the editable source and generated XML is not hand-edited. The author does not execute runtime nodes; domain data uses metadata and artifacts rather than new runtime node types or large blackboard values.

## `xc-orchestration-runtime`

[Canonical contract](../../../skills/xc-orchestration-runtime/SKILL.md)

- **Invoke when:** a workflow needs scheduling, node transitions, controlled state updates, subtree embedding, integrity operations, snapshots, or persistence.
- **Purpose:** provide the domain-neutral control plane for managed runtime trees and transactional workshop checkpoints.
- **Portable public entry:** `orchestration.py` lifecycle commands such as `init`, `next`, `control-packet`, `start`, `complete`, `fail`, and `block`, plus documented query and recovery commands including `unblock`, `retry-failed`, and `reopen`. Opt-in completion adds repeated `--check-result-json`; opt-in gates add `--gate-outcome` and `--decision`.
- **Prerelease package adapter:** a matching repository package exposes the same 23 commands as `xc runtime <command> ...`. This is direct application execution, not daemon transport, and it is not a published consumer entry point.
- **Typical usage:** initialize a template, request ready work, read the selected leaf's scoped packet, start only that executable leaf, and terminate it with concise evidence and declared artifacts. When the same approved leaf contract should run after failure, `retry-failed --reason` archives the attempt and restores ordinary scheduling.
- **Boundaries:** managed XML is never read or edited directly; workers execute exactly one node, source projection is not start authority, invalid integrity requires explicit repair, and successful trees remain sealed until an approved reopen.

### Runtime Implementation Ownership

`src/xcoding/runtime/` is the editable source for the runtime core, Runtime
Application Service, and complete command specification. The package CLI and
legacy Skill adapter both call that application service; neither owns
transaction logic.

The complete runtime Skill remains independently installable. Its
`scripts/_runtime_compat/` directory is a deterministic generated copy of the
canonical modules, and `runtime_core.py` plus `orchestration.py` are
compatibility aliases or adapters. Generation checks reject drift, and Bundle
checks require the complete payload. Consumers must not edit the payload as a
second implementation.

### Control Contracts

`metadata.control_packet.*` declares leaf-only source categories, thresholds, and selected blackboard scalars. Missing declarations return `control_packet_not_declared`; unresolved selectors, non-terminal sources, insufficient source or artifact counts, or missing selected keys return `control_packet_unavailable` without a partial packet.

`metadata.completion.*` may require `summary`, `validation`, artifact cardinality and path, and normalized check receipts. Malformed, oversized, duplicate, or undeclared receipts return `invalid_check_result`; unmet fields, artifacts, required checks, subjects, or facts return `completion_requirements_failed`. Receipts are untrusted unsigned self-reports. The runtime compares shape and declared values but does not run validators, bind a claimant, or prove execution; a fabricated exact match is accepted.

`metadata.gate.*` declares allowed structured outcomes, whether a decision is required, and an optional outcome key. Completion can return `gate_outcome_required`, `invalid_gate_outcome`, `gate_decision_required`, `gate_outcome_conflict`, or `gate_outcome_not_allowed`. The outcome and its declared blackboard key are written atomically, but runtime does not authenticate the CLI caller.

All three recognized prefixes fail closed with `invalid_control_metadata` for unknown keys, invalid owners, malformed values, or incomplete declarations during author validation, runtime validation and initialization, and dynamic `add-node`. These extensions are opt-in within `schema_version=1`: existing schema-version-1 nodes without the new metadata retain legacy command and result behavior. Earlier schema formats remain unsupported.

The runtime provides no trusted execution, claim binding, typed blackboard, host-tool mediation, or model-specific profile. It also cannot prevent ordinary host-tool use before `start`; these remain host and caller responsibilities.

`retry-failed` is explicit attempt recovery, not automatic retry policy. It
accepts only failed task or gate leaves, preserves the prior result and
artifacts in ordered history, supports `--expected-revision`, and does not
reset successful or running siblings. Node queries and snapshots expose the
history; retry-aware artifact entries include their attempt number. Switch and
loop failures generated by the engine are not eligible.

## `xc-orchestration-viewer`

[Canonical contract](../../../skills/xc-orchestration-viewer/SKILL.md)

- **Invoke when:** a user asks to open, monitor, or visualize managed runtime progress.
- **Purpose:** provide a script-free facade over the runtime-owned, loopback-only, read-only viewer.
- **Public entry:** launch the runtime `viewer_server.py` with `--tree`; use `runtime_skill_dir` for a non-sibling installation and `--allow-root` only for additional permitted directories.
- **Typical usage:** start the detached local server, inspect snapshots in the browser, pan or zoom the graph, and download a complete SVG.
- **Boundaries:** it owns no parser, state machine, server, or frontend and exposes no mutation endpoint; selected trees and native-picker authorization remain narrowly scoped.
