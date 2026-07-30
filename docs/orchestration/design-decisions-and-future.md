**Language:** **English** | [简体中文](../zh-CN/orchestration/design-decisions-and-future.md)

# Design Decisions and Future Possibilities

This page separates current design rationale from speculation. Current behavior is defined by the tracked [`runtime`](../../skills/xc-orchestration-runtime/SKILL.md), [`author`](../../skills/xc-orchestration-author/SKILL.md), and [`viewer`](../../skills/xc-orchestration-viewer/SKILL.md) contracts.

## Current Design Decisions

### Tree-First Control

XC uses hierarchical sequence, parallel, switch, dynamic-group, and loop composition. Limited dependencies cover necessary cross-branch prerequisites without turning the runtime into a general DAG engine.

Tradeoff: tree structure is easier to explain, stabilize, visualize, and delegate locally, while highly connected dependency graphs are intentionally awkward.

### Deterministic Runtime, Domain-Owned Meaning

Runtime owns scheduling, transition guards, aggregation, integrity, and persistence. Domain Skills own instructions, acceptance, review authority, failure policy, and artifact meaning.

Tradeoff: adding a new domain workflow does not require changing the runtime, but domain packages must write complete node contracts instead of relying on runtime knowledge.

### Four Control Node Types

`composite`, `task`, `gate`, and `loop` cover runtime control semantics. Roles such as review, research, writing, and repair remain domain labels.

Tradeoff: templates stay portable and the runtime avoids a growing business-type enumeration, at the cost of requiring readers to inspect role and node instructions for domain meaning.

### Small Conditions

Conditions support only truthiness, negation, equality, and inequality. Complex judgment belongs in an executable task that writes a simple blackboard result.

Tradeoff: templates remain testable and side-effect-free, while an extra task may be needed for a complex decision.

### Bounded End-of-Iteration Loops

Loops decide whether to continue only after an iteration finishes, and every loop has a maximum and limit outcome.

Tradeoff: review/rework convergence is deterministic and recoverable, while imperative mid-iteration control is unavailable.

### Concentrated Main-Session Gates

User interaction is represented by `gate executor=main` after relevant evidence has been gathered.

Tradeoff: user decisions are focused and globally visible, while templates must deliberately place gates before consequential work.

### Compact Blackboard, Durable Artifacts

The blackboard holds short control values. Reports and other rich output live in workshop artifacts or external target systems.

Tradeoff: runtime state stays compact and schedulable, while consumers must follow declared artifact paths to inspect full evidence.

### Single-Node Workers

The main session starts work; each worker executes one node and reports its terminal result; the main session verifies state.

Tradeoff: delegation boundaries and parallel ownership remain clear, while the runtime does not provide a worker pool or automatic capability matching.

### Managed Local Persistence

Runtime trees are managed schema-version-1 XML accessed through public operations. Writes use validation, locking, revisions, atomic replacement, and checksum verification.

Tradeoff: local operation is inspectable and recoverable, while arbitrary persistence backends are not supported.

### Transactional Checkpoints and Sealing

When automatic workshop commits are enabled, a terminal checkpoint accepts its tree transition and declared artifacts together. Commit or render failure restores prior managed state. Successful roots are sealed and require an explicit, reasoned reopen operation.

Tradeoff: accepted state and checkpoint evidence cannot silently diverge, while Git or rendering failures block terminal acceptance rather than becoming warnings.

### Read-Only Viewer

The Viewer consumes snapshots and cannot mutate orchestration state. It binds to loopback, defaults to port `20668`, and uses custom static browser code rather than D3.

Tradeoff: inspection has a small security and correctness surface, while operators must use runtime commands for changes.

## Current Non-Goals

The current system does not provide:

- A general DAG engine or policy-pluggable scheduler.
- Generic retries, timeouts, token/time/cost budgets, or retry metrics.
- Worker pools, capability matching, or forced worker cancellation.
- Runtime control signals for breaking loops, skipping siblings, terminating subtrees, or aborting a run.
- A standalone typed artifact index or artifact storage service.
- Event sourcing or a runtime event log.
- Arbitrary persistence formats, a persistence-neutral core, or a remote orchestration service.
- A writable Viewer or network-exposed dashboard.

Executors named `tool` and `service` do not imply a capability registry or automatic remote execution. The `artifacts` command reports terminal declarations; it is not an indexed provenance database.

## Non-Normative, Uncommitted Possibilities

Everything in this section is non-normative. It is not a roadmap, commitment, schedule, compatibility guarantee, or approved design. A possibility becomes part of XC only through a separately approved workflow change with contracts, tests, and migration analysis.

Possible areas for investigation include:

- Better author diagnostics that explain invalid references, unreachable branches, or surprising first-ready results.
- Additional read-only snapshot summaries and comparison tools derived from existing runtime state.
- Accessibility and large-tree navigation improvements in the local Viewer.
- More reusable examples of bounded review, dynamic-matrix, and gate-controlled workflow composition.
- Narrow additions to validated condition or template tooling when repeated real workflows demonstrate a generic need.

No implementation language, service architecture, alternate persistence backend, scheduler plugin system, budget model, worker-pool design, artifact-index model, cancellation protocol, or event-sourcing model is selected or promised. Such topics require independent evidence and approval rather than inference from this page.

## How Decisions Evolve

Changes to orchestration semantics must preserve domain neutrality and public boundaries. They require:

1. A demonstrated recurring need that cannot be handled cleanly by domain templates.
2. An explicit contract for state, failure, recovery, and compatibility.
3. Author validation and runtime transition tests.
4. Viewer updates only when the read-only snapshot contract changes.
5. Documentation that clearly distinguishes released behavior from remaining possibilities.
