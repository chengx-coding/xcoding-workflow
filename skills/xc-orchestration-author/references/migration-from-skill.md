# Migrating a Prose Workflow Skill

Move a complex prose-heavy workflow into a domain template package while leaving domain knowledge in its own Skill.

## Migration Steps

1. Extract workflow stages, task prerequisites, user decisions, parallel opportunities, failure paths, review cycles, and output artifacts.
2. Classify each item:
   - `task` for executable work.
   - `gate` for main-session user decisions.
   - `composite` for sequence, parallel, switch, or dynamic grouping.
   - `loop` for a bounded end-of-iteration cycle.
3. Write `assets/flow-spec.json` with `template_id` fields and `local:` references.
4. Build a managed `assets/orchestration-template.xml`.
5. Replace lengthy procedural text in the domain `SKILL.md` with a runtime initialization command, a `next -> delegate -> update` driver loop, domain-reference links, and artifact and blackboard contracts.
6. Smoke-test `validate-template`, `init`, and `next`.

## Do Not Migrate

- Do not carry forward deprecated demo node types (`root`, `phase`, `group`, `review`, `expand`, or `tool`).
- Do not copy the shared runtime script or standalone HTML viewer into the domain Skill.
- Do not preserve old runtime XML through an adapter. Build a new managed
  template and run a new instance.
- Do not encode domain assessment logic in `when`; use a preceding task to calculate a blackboard decision, then use `switch` or a simple condition.

## Completion Criteria

The resulting template validates, starts through `xc-orchestration-runtime`, returns the expected ready node or nodes, and can be viewed through the runtime-owned snapshot/viewer path without direct XML access.
