**Language:** **English** | [Simplified Chinese (简体中文)](../zh-CN/orchestration/authoring.md)

# Authoring Managed Workflows

[`xc-orchestration-author`](../../skills/xc-orchestration-author/SKILL.md) converts an approved workflow design into a managed template that the runtime can instantiate. It owns design, JSON flow specifications, construction, and template validation. It does not execute nodes or own domain policy.

## Authoring Flow

The supported flow is:

1. Establish the workflow purpose, inputs, outputs, user decisions, failure policy, and compatibility constraints.
2. Decompose the workflow into deterministic control structure and self-contained leaves.
3. Create or revise a JSON flow specification.
4. Validate the flow specification.
5. Build the managed schema-version-1 template.
6. Validate the template.
7. Smoke-test it through runtime `init` and `next`.

The public commands are:

```powershell
python <author-skill-dir>/scripts/template_builder.py new-spec --out <flow-spec>
python <author-skill-dir>/scripts/template_builder.py validate-spec --spec <flow-spec>
python <author-skill-dir>/scripts/template_builder.py build --spec <flow-spec> --out <template>
python <author-skill-dir>/scripts/template_builder.py validate-template --template <template>
```

The [template design method](../../skills/xc-orchestration-author/references/template-design-method.md) provides the detailed decomposition rules.

## Design Method

Use the smallest control structure that expresses the approved behavior:

- `composite mode=sequence` for ordered stages.
- `composite mode=parallel` for independent work with non-overlapping write ownership.
- `composite mode=switch` for deterministic routing from a previously computed blackboard value.
- `composite role=dynamic-group` when the child set is discovered at runtime.
- `gate executor=main` for concentrated human decisions.
- `loop` for bounded end-of-iteration review or repair.

Keep domain meaning in `role`, `metadata.*`, instructions, deliverables, and acceptance. Do not create runtime node types for review, writing, testing, repair, phases, or expansion.

Large content belongs in artifacts. The blackboard should contain only compact values that influence routing or later decisions. If a condition requires complex analysis, put that analysis in a task and write a simple result key for a condition or switch.

## Flow Specifications and Template IDs

The JSON flow specification is the editable source used by the deterministic builder. Every node has a stable, readable, kebab-case `template_id`. Templates never contain runtime IDs.

Dependencies use template-local references:

```text
depends_on_template="local:prepare"
```

The author validates local uniqueness and resolvability. Runtime instantiation rewrites each local reference into the correct instance-specific runtime ID and retains provenance.

Subagent leaves must provide `instructions`, `deliverables`, and `acceptance`. Gates use `executor=main`; composite and loop nodes also use `executor=main`. Loops require a positive maximum iteration count and an explicit limit outcome. Switches require a key and mutually exclusive case/default children.

## Conditions, Dynamic Work, and Loops

Conditions use the runtime's intentionally small expression set. They default to `when.policy=reactive`. Use `when.policy=latched` when a one-time optional branch must remain skipped even if a shared value later changes.

Dynamic groups should make lifecycle explicit: discover work, append nodes or subtrees, then close the group. An author should define ownership so parallel workers do not edit the same output.

Loops evaluate break and continue conditions only after an iteration's children finish. Every loop is bounded. Do not design around internal loop control signals, generic retry transitions, or forced worker cancellation; those are not runtime capabilities.

## Domain Package Boundary

A domain Skill may own:

```text
assets/
  orchestration-template.xml
references/
  runtime-usage.md
  subagent-contract.md
  artifact-contract.md
  blackboard-contract.md
```

This is a responsibility pattern, not a requirement to create empty files. The package documents runtime-tree location, blackboard keys and allowed values, artifact ownership, single-node worker prompts, and gate behavior.

The package must not copy the runtime state machine, XML parser, Viewer server, or generic orchestration scripts. See the [template package contract](../../skills/xc-orchestration-author/references/template-package-contract.md).

## Validation and Smoke Tests

`validate-spec` catches malformed flow specifications before generation. `build` deterministically creates a managed template with access and integrity metadata. `validate-template` checks structural rules and runtime compatibility.

A successful build is not sufficient. Initialize a disposable runtime tree through the runtime public command and call `next`. Verify that the first leaf or parallel batch, gate placement, conditions, and dynamic-group state match the design. Exercise important branch, loop-limit, and failure paths when the template's risk warrants it.

For a prose-oriented Skill migration, preserve domain guidance while replacing its procedural program counter with the managed template and public runtime driver. Do not retain an unmanaged compatibility copy of the old runtime structure. See [migration from a prose workflow](../../skills/xc-orchestration-author/references/migration-from-skill.md).

## Authoring Review Checklist

Before publishing a template, confirm:

- Each leaf is independently understandable and has an owned deliverable.
- User gates occur after evidence collection and before consequential work.
- Parallel branches cannot conflict on files or external resources.
- Conditions are simple, side-effect-free routing decisions.
- Dynamic groups are eventually closed.
- Loops are bounded and have an explicit limit result.
- Failures and blockers have an intentional recovery path.
- Runtime behavior remains domain-neutral.
- `validate-spec`, `build`, `validate-template`, runtime `init`, and runtime `next` pass.
