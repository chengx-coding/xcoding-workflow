[简体中文](../zh-CN/workflows/evolving.md)

# Evolving XC

Workflow maintenance uses the same evidence, approval, implementation, verification, and review discipline as product work. The [`xc-workflow-evolution`](../../skills/xc-workflow-evolution/SKILL.md) entry point first separates portable core changes from project-specific bridge changes.

## Choose The Evolution Scope

| Scope | Use it for |
| --- | --- |
| `portable-core` | Generic Skill contracts, references, scripts, assets, and shared workflow behavior |
| `project-bridge` | One project's managed workflow guidance and project-specific conventions |
| `agent-export` | Canonical portable agents, target metadata, exporter behavior, and generated definitions |
| `orchestration-template` | Managed flow specifications, generated templates, scheduling structure, and gates |
| `health-check` | Focused maintenance that verifies workflow assets and their derived outputs |

Broad architecture changes require evidence, viable alternatives, independent review, and an explicit user gate before implementation.

## Change Canonical Sources First

### Skills

Edit generic packages under `skills/xc-*/`. Keep frontmatter, bodies, references, templates, and agent-facing instructions in English and free of consumer-project facts. Preserve public parameters and cross-Skill boundaries unless the approved change deliberately revises them.

After a Skill change, run the tracked [Skill sync script](../../build_agents.py) so the checkout-local Agent discovery adapter matches the canonical packages. Do not repair only the adapter copy.

### Agents

Edit persistent portable definitions under `agents-src/agents/`. Express tool, model, permission, sandbox, and frontmatter differences as target metadata rather than forking the shared body.

Run the tracked [agent exporter](../../agents-src/export_agents.py) to regenerate Claude Code, OpenCode, and Codex definitions. Generated target files are reviewable outputs, not editing surfaces.

### Orchestration

Use [`xc-orchestration-author`](../../skills/xc-orchestration-author/SKILL.md) to change an approved JSON flow specification, validate it, and rebuild the managed template. Domain Skills own node instructions, acceptance criteria, and artifacts; the runtime remains domain-neutral.

Do not hand-edit generated templates or managed runtime trees. Runtime state changes go only through the [`xc-orchestration-runtime`](../../skills/xc-orchestration-runtime/SKILL.md) public interface.

### Project Bridge

A project-bridge change updates the managed conceptual path `.xcoding/WORKFLOW.md` through document evolution, validation, review, and any required gate. It does not copy project commands, repository facts, or business rules into portable Skills.

## Verify Every Derived Surface

| Changed surface | Required evidence |
| --- | --- |
| Skill package | Naming and frontmatter validation, public-contract and resource-path checks, Agent discovery sync, focused tests, and applicable broader tests |
| Canonical agent or exporter | Export all supported targets, run `python agents-src/export_agents.py --check`, and review every generated diff |
| Orchestration flow or template | Validate the flow specification and template, then smoke-test the public runtime path through `init` and `next`; broaden tests for affected scheduling, gates, loops, recovery, integrity, or concurrency |
| Project bridge | Managed document validation, independent review when required, and checks declared by that bridge |
| Public documentation | Structural and link checks plus independent English/Chinese semantic review |

Run focused checks first, then broaden verification according to the changed contract and blast radius. A failing generated-file check is fixed at its canonical source.

## Documentation Impact And Languages

Every XC iteration evaluates whether its behavior, commands, paths, boundaries, or examples affect public documentation. Update every affected English page and its exact `docs/zh-CN/` mirror in the same change, including both directions of the language switch and any navigation that names the page.

The English page is normative; the Chinese page must preserve the same topic, factual boundary, and material information without requiring line-by-line translation. Automated checks establish topology, links, Git visibility, and catalog invariants, but an independent bilingual review still verifies semantic equivalence.

Public pages link only files available in a clean checkout. They do not link workshop state, local Agent discovery assets, project instructions, or other ignored and excluded maintenance files.

The project does not currently publish a formal Python-version or Agent-host compatibility matrix. Documentation and workflow changes must not imply compatibility guarantees that have not been defined and verified.
