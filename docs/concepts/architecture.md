**Language:** **English** | [简体中文](../zh-CN/concepts/architecture.md)

# Architecture

## Mission

XC is a portable, Skill-driven coding workflow. It covers discovery, design, implementation, diagnosis, verification, review, repair, and delivery while keeping project-specific policy outside the generic workflow core.

The repository is the source for workflow capabilities, not a consumer project's source tree or workshop history.

## Canonical Sources

The repository has two canonical workflow authoring surfaces:

- `skills/xc-*/` owns generic workflow Skills. A package's `SKILL.md` is its public discovery and operation contract; its `references/`, `scripts/`, and `assets/` support that contract.
- `agents-src/agents/` owns persistent, portable subagent definitions. The tracked [`xc-delegated-agent` definition](../../agents-src/agents/xc-delegated-agent.md) is an example of a tool-neutral canonical agent.

The canonical agent definitions under `agents-src/agents/` follow one naming rule. The rule binds every canonical agent definition in that directory, not only the current one.

- **`xc-` prefix.** A canonical agent identifier begins with `xc-`, and the prefix belongs to both the file stem (the canonical filename without `.md`) and the frontmatter `name`. The identifier therefore shares the portable `xc-` namespace with `skills/xc-*/`. Unlike the Skill side, no mechanical check enforces this prefix on the agent side.
- **`-agent` suffix.** The identifier form is `xc-<descriptive-name>-agent`. The handle a user invokes is the emitted `name` in Claude Code, Codex, and Trae, or the OpenCode filename, never the path, so the word `agents` in an install directory is redundant as a path but not as a handle. The suffix is what separates an agent identifier from a Skill identifier, since no package under `skills/` ends in `-agent`.
- **Stem and name are equal.** The canonical file stem equals the frontmatter `name` verbatim. Claude Code, Codex, and Trae emit that name verbatim, so `stem == canonical name == emitted name` holds there by construction. No mechanical check enforces the equality: the exporter requires only that `name` and `description` are non-empty, and neither its check mode nor the build-time exact-set policy compares a stem with a name. Changing only one of the two sides leaves a divergent state that every existing guard accepts.
- **Hosts that emit no name.** The OpenCode output carries no `name` field, so the filename is its identity and the invariant degenerates to `stem == generated filename`, which the stem-based export already guarantees without reading any field. This describes what this repository emits; whether OpenCode itself resolves that filename as a user-visible handle is external program behavior that no tracked file here states.
- **H1 heading.** A canonical agent definition writes its identifier verbatim as the H1, in backquoted lowercase form, for example `` # `xc-delegated-agent` ``. The H1 reaches all four generated bodies verbatim, so it is a visible surface of the same identity chain.
- **Character class.** The identifier matches `[a-z0-9]+(?:-[a-z0-9]+)*`: ASCII lowercase letters and digits, with a single hyphen between segments. The class constrains the file stem and the frontmatter `name`, which the stem-equals-name rule already makes one value; the backquotes in the H1 are not part of the constrained value. No check enforces this class today.
- **Scope.** The rule applies to every canonical agent definition under `agents-src/agents/`. The build derives the expected generated file set from the canonical stem set, so any rule about a stem is a set-level rule; the current inventory of one element is a present fact, not a design decision.
- **Documentation-only strength.** The rule is documentation only: it adds no mechanical check, and its entire force is documentation discipline. Retired names stay unblocked, because the Skill side has a retired-package blocklist and the agent side has no equivalent, so a retired agent name can return without failing anything. In particular, since no tool compares a file stem with its frontmatter `name`, a future one-sided change still passes `python agents-src/export_agents.py --check`.

Canonical sources are changed before anything derived from them. Skills communicate through Skill names and documented public parameters. One Skill does not reach into another Skill's private references or scripts.

## Generated Outputs And Adapters

`agents-src/claude-agents/`, `agents-src/opencode-agents/`, `agents-src/codex-agents/`, and `agents-src/trae-agents/` are generated target-specific agent definitions. The [agent exporter](../../agents-src/export_agents.py) validates canonical definitions and reproduces those outputs.

Agent-host discovery locations and installation directories are adapters, not new sources of truth. For example, the tracked [Skill sync script](../../build_agents.py) mirrors canonical Skill packages into a checkout-local discovery directory. Changes still begin in `skills/xc-*/`.

This separation keeps tool-specific metadata, permissions, and file formats at the edge while the shared behavior remains portable.

## Skill-local workers and the delegated Agent

[`xc-delegation`](../../skills/xc-delegation/SKILL.md) lets an owning Skill keep a private worker profile under `assets/workers/<profile-id>/` while reusing the persistent `xc-delegated-agent` supplied to every supported host. A private profile is not a second persistent Agent definition: it is resolved only through the owning Skill root, validated against strict schemas, and compiled into one deterministic dispatch envelope for one running node attempt.

The Skill-local source profile is current-only: its root object carries no `schema_version`, and a retired root version field is rejected rather than silently migrated. The main session obtains a read-only assignment packet from the runtime, then `xcoding delegate prepare` intersects six independent capability layers: the profile request, XC ceiling, project ceiling, node-owned authorization, caller narrowing, and host statement. No layer can widen an earlier denial. Dynamic overlays can only narrow the resolved profile, and an invalid or unsupported v1 input fails closed without falling back to a prompt-defined role.

`xc-delegated-agent` exposes two explicit compatibility modes. `prepared-profile` accepts only a dispatch-authoritative prepared envelope and uses the assigned in-process terminal binding for exactly one allowed node result. `legacy-prompt` accepts an explicitly selected prompt-defined role and never claims v1 validation or enforcement. A private role that becomes shared across Skills, directly user-selectable, or dependent on a distinct persistent model or permission identity is promoted to a canonical definition under `agents-src/agents/`.

Host capability statements are build and setup resources, not proof that a third-party host enforces the envelope. The current four statements are `validated-only` with unverified adapter versions; network and secret capabilities remain unsupported. `enforced` requires matching fixed-version end-to-end evidence.

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
Runtime Application Service, persistence transactions, shared 26-command
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
checks, accepts only launch-time runtime files, exposes ten typed read-only
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
