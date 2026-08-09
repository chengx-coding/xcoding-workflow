**Language:** **English** | [简体中文](../zh-CN/orchestration/overview.md)

# Orchestration Overview

XC orchestration turns a complex, long-running Agent workflow into a managed tree with deterministic scheduling and durable state. Markdown remains responsible for purpose, policy, domain methods, node instructions, and acceptance criteria. The orchestration services are responsible for executable structure, state transitions, persistence, integrity, and inspection.

This separation is primarily about context and control. The main session can request only the next ready work instead of loading an entire workflow. A worker receives one self-contained node instead of interpreting the whole process. Deterministic operations such as sequence ordering, condition evaluation, loop progression, and parent-state aggregation stay in code rather than repeated model judgment.

## Service Boundaries

The architecture has three public services:

- [`xc-orchestration-runtime`](../../skills/xc-orchestration-runtime/SKILL.md) is the domain-neutral control contract. The required `xcoding` package owns runtime state, scheduling, transitions, integrity, controlled persistence, snapshots, and the local Viewer implementation.
- [`xc-orchestration-author`](../../skills/xc-orchestration-author/SKILL.md) turns an approved workflow design into a validated schema-version-1 template. It owns flow specifications, template construction, and authoring validation, but does not execute work.
- [`xc-orchestration-viewer`](../../skills/xc-orchestration-viewer/SKILL.md) is a script-free discovery facade for human inspection. The `xcoding` package owns the server, snapshot interpretation, and frontend implementation.

Domain Skills own the meaning of the work. They define templates, task instructions, gates, artifact contracts, blackboard keys, acceptance criteria, and domain references. They invoke the runtime through public operations and do not copy its scheduler, state machine, parser, or Viewer.

The required prerelease Python package also exposes `xcoding daemon serve`.
It exposes only the runtime's typed read-only query facade over
bearer-authenticated loopback HTTP and bounded summary SSE. It is not another
state owner and cannot perform runtime transitions. `xcoding runtime` remains
the direct mutation boundary. The Skills have no package-free fallback.

The main session is the orchestrator. It initializes or resumes a tree, asks for ready nodes, starts delegated work, handles `executor=main` gates, and verifies results. It may execute work explicitly assigned to `executor=main`; it is not restricted to delegation alone. A subagent is a single-node worker and does not inspect siblings, future nodes, or global control flow.

## Design Influences

The model combines selected ideas from several established approaches:

- Behavior trees contribute sequence and parallel composition, hierarchical status, and a blackboard.
- Workflow systems contribute explicit dependencies, durable task state, and artifacts.
- Hierarchical task decomposition contributes goal-to-task structure.
- State machines contribute guarded lifecycle transitions.
- Worker-queue systems contribute a scheduler/worker boundary.

These are design influences, not claims that XC implements any one formal model in full. The system is tree-first, with limited explicit dependency edges. It is not a general DAG engine.

## Durable and Public Boundaries

Managed templates and runtime trees are current durable XML representations, but XML is not an Agent-facing editing interface. Agents use the author and runtime public commands. The operation protocol and deterministic semantics are the public abstraction.

Runtime is deliberately domain-neutral. It understands four control node types: `composite`, `task`, `gate`, and `loop`. Business concepts such as investigation, review, writing, testing, or repair belong in `role`, `metadata.*`, and node contracts.

Shared information is split by size and purpose:

- The blackboard holds short values that affect later scheduling or decisions.
- Artifacts hold reports, plans, code changes, verification evidence, and other rich output.
- Runtime records declared artifact paths on terminal node operations; it does not provide a separate artifact store.

The Viewer is read-only. It consumes runtime snapshots and exposes no lifecycle or blackboard mutation endpoints. Runtime state changes go through `xcoding runtime`.

The Viewer and package daemon are distinct surfaces. The Viewer provides a
browser UI, local registry, native picker and SVG download. The daemon has no
UI or picker, accepts only launch-time runtime files, requires a bearer token,
and serves local tools. Neither surface exposes runtime mutation.

## Reusable Workflow Patterns

The control primitives can be composed into recurring patterns without making them runtime syntax:

### Investigation, Synthesis, Gate, Execution

Run independent investigations in parallel, synthesize the evidence, present one concentrated main-session gate, then execute the approved work. This keeps user decisions evidence-backed and avoids scattered worker questions.

### Dynamic Matrix

Discover a set of targets, append one self-contained node or embedded subtree per target to an open dynamic group, explicitly close the group, execute its children, and aggregate the results. Parallel children must have independent write ownership.

### Review and Rework

Place role-based review and conditional rework tasks in a bounded loop. Review findings and closure authority remain domain contracts; runtime only supplies loop, condition, state, and blackboard mechanics.

### Gate-Controlled Risk

Analyze risk, prepare explicit options, collect a user decision in a gate, execute the selected option, and verify the result. Gates are concentrated control points, not a substitute for self-contained worker instructions.

## What to Read Next

- [Runtime model](runtime-model.md) explains objects, IDs, scheduling, state, loops, recovery, and persistence.
- [Authoring](authoring.md) explains flow specifications, template design, validation, and smoke tests.
- [Viewer](viewer.md) explains the read-only local server, UI, security boundary, and lifecycle.
- [Design decisions and future possibilities](design-decisions-and-future.md) records current tradeoffs, non-goals, and explicitly uncommitted ideas.
