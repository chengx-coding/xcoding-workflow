**Language:** **English** | [简体中文](../zh-CN/concepts/architecture.md)

# Architecture

## Mission

XC is a portable, Skill-driven coding workflow. It covers discovery, design, implementation, diagnosis, verification, review, repair, and delivery while keeping project-specific policy outside the generic workflow core.

The repository is the source for workflow capabilities, not a consumer project's source tree or workshop history.

## Canonical Sources

The repository has two canonical workflow authoring surfaces:

- `skills/xc-*/` owns generic workflow Skills. A package's `SKILL.md` is its public discovery and operation contract; its `references/`, `scripts/`, and `assets/` support that contract.
- `agents-src/agents/` owns persistent, portable subagent definitions. The tracked [delegate agent definition](../../agents-src/agents/delegate-agent.md) is an example of a tool-neutral canonical agent.

Canonical sources are changed before anything derived from them. Skills communicate through Skill names and documented public parameters. One Skill does not reach into another Skill's private references or scripts.

## Generated Outputs And Adapters

`agents-src/claude-agents/`, `agents-src/opencode-agents/`, `agents-src/codex-agents/`, and `agents-src/trae-agents/` are generated target-specific agent definitions. The [agent exporter](../../agents-src/export_agents.py) validates canonical definitions and reproduces those outputs.

Agent-host discovery locations and installation directories are adapters, not new sources of truth. For example, the tracked [Skill sync script](../../build_agents.py) mirrors canonical Skill packages into a checkout-local discovery directory. Changes still begin in `skills/xc-*/`.

This separation keeps tool-specific metadata, permissions, and file formats at the edge while the shared behavior remains portable.

## Package, Bundle, And Runtime Application Infrastructure

The repository also contains product package and release-verification infrastructure in `pyproject.toml`, `src/xcoding/`, `build_support/`, `scripts/`, and `.github/`. It builds the `xcoding-workflow` package and immutable Bundle and verifies candidate-independent package contracts. This is a repository build boundary, not another workflow authoring surface.

The Bundle is a build-time snapshot. `skills/xc-*/` remains the only canonical
source for Skills, while package runtime and Viewer implementation/resources
live under `src/xcoding/`. `agents-src/agents/` remains the only canonical
source for persistent agent definitions. Generated host-specific agent
definitions are only validated build inputs for Bundle adapters; they are not
sources of truth. `build_support/host_adapters.json` only declares how those
generated inputs map into the Bundle. The current Bundle has no Viewer
implementation partition.

`src/xcoding/runtime/` is the editable source for the runtime tree model,
Runtime Application Service, persistence transactions, shared 23-command
specification, typed read-only query facade, and default template.
`src/xcoding/viewer/` owns the Viewer server, picker, lifecycle, and static
frontend. `src/xcoding/daemon/` owns the authenticated read-only tool API.

The matching `xcoding` package is required. `xcoding runtime` directly invokes
the Runtime Application Service; `xcoding viewer` and `xcoding daemon` expose
the other package-owned surfaces. The runtime Skill retains only a thin legacy
`orchestration.py` adapter that executes `xcoding runtime` through the
installed console command. It returns `xcoding_unavailable` and has no local
fallback when the tool is missing.

`xcoding daemon serve` is an optional local read-only transport. It binds only
to `127.0.0.1`, requires a process-lifetime bearer token and exact Host/Origin
checks, accepts only launch-time runtime files, exposes nine typed read-only
queries, and streams bounded non-durable SSE summaries. `xcoding runtime`
remains direct local execution and does not discover or start the daemon.
`xcoding viewer` remains a separate browser inspection surface.

This infrastructure is not published and provides no public package source.
Current use therefore requires a maintainer-provided validated local wheel in
addition to Skill installation. Required external Stage 1 matrix evidence is
still unavailable, so the result remains `unknown` and `no-go`; no package,
platform, Python, or Agent-host compatibility is promised. The daemon provides
no remote bind, runtime mutation service, durable operation journal, replay,
service installation, discovery, or default transport switch. Later mutation,
remote transport, or release work requires separate approval.

## Generic Core And Project Bridge

Generic Skills define reusable lifecycle behavior. They do not hard-code a consumer project's language, framework, repository layout, build commands, test tools, documentation policy, business rules, or project-only capabilities.

Each consumer project supplies those choices through the conceptual bridge path `.xcoding/WORKFLOW.md`. Optional project knowledge guidance lives at `.xcoding/KNOWLEDGE.md`. These workshop-local paths are deliberately not public documentation links.

The effective flow is:

```text
user request
  -> generic xc-* lifecycle contract
  -> project bridge and declared project knowledge
  -> project code, tests, and managed workshop
```

The generic core decides when project knowledge is needed. The bridge supplies the facts; it cannot override runtime safety, public Skill contracts, or orchestration access controls.

## Main Session, Worker, And Public Boundaries

The main session is the orchestrator. It opens or resumes the work order, asks the runtime for ready work, starts executable nodes, handles user gates, delegates one node at a time, and verifies runtime state after a worker returns.

A worker receives one running node and its bounded inputs. It executes only that node, writes declared artifacts, and reports completion, failure, or blocking through the public runtime interface. It does not inspect sibling or future nodes, change global control flow, or directly read managed runtime files.

The [orchestration runtime contract](../../skills/xc-orchestration-runtime/SKILL.md) is the only boundary for managed tree reads, transitions, scheduling, integrity operations, and snapshots. Large analysis and reports belong in artifacts; the runtime blackboard holds only short values that affect control flow.

These boundaries make lifecycle state resumable and auditable without coupling domain Skills or workers to the runtime's storage format.
