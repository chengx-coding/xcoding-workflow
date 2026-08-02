---
name: "xc-orchestration-author"
description: "Designs, validates, and builds managed orchestration templates. Invoke when a workflow needs a new template or prose flow must become runtime-controlled orchestration."
---

# XC Orchestration Author

`xc-orchestration-author` converts an approved workflow design into a managed template that `xc-orchestration-runtime` can instantiate. It owns template design and JSON flow specifications; it does not execute runtime nodes.

## Template Model

Templates are managed `schema_version="1"` XML artifacts. Every node uses a stable `template_id`, a control `type` of `composite`, `task`, `gate`, or `loop`, an optional semantic `role`, and an `executor` of `main`, `subagent`, `tool`, or `service`.

Template dependencies use `depends_on_template="local:<template_id>"`. The runtime rewrites them to globally unique runtime node IDs. Use `metadata.*` for domain-specific classification rather than adding runtime node types.

Conditional nodes default to `when.policy=reactive`; set
`when.policy=latched` for a one-time optional branch that must not reopen when
shared control values later change. A `role=dynamic-group` starts open and may
declare `dynamic.state=closed` only when the template intentionally contains
no future dynamic work.

The runtime supports sequence, parallel, switch/case, simple `when` conditions, explicit dependencies, dynamic nodes, and end-of-iteration loop conditions. Loop-local `break` and `continue` signals are not part of the current contract.

## Control Metadata

Flow-spec leaves may opt in to the runtime's `metadata.control_packet.*`, `metadata.completion.*`, and `metadata.gate.*` contracts. Values that represent arrays MUST be compact JSON array strings. Control-packet and completion declarations belong only to `task` or `gate` leaves; gate declarations belong only to `gate` leaves.

The author validates every recognized key, owner, required pairing, and value during `validate-spec`, before any template is built. A recognized-prefix error returns `invalid_control_metadata` with stable, key-sorted `details.violations`; `build` rejects the same declaration without creating or replacing its output. Unknown metadata outside the three recognized prefixes remains valid and is preserved.

## Workflow

1. Extract phases, serial and parallel work, gates, review loops, artifacts, and blackboard variables from the approved workflow design.
2. Create or revise a JSON flow specification.
3. Validate the specification.
4. Build the managed template.
5. Smoke-test it through `xc-orchestration-runtime init -> next`.

```powershell
python "$SKILL_DIR/scripts/template_builder.py" new-spec --out <flow_spec>
python "$SKILL_DIR/scripts/template_builder.py" validate-spec --spec <flow_spec>
python "$SKILL_DIR/scripts/template_builder.py" build --spec <flow_spec> --out <template_path>
python "$SKILL_DIR/scripts/template_builder.py" validate-template --template <template_path>
```

Template build writes access policy and integrity metadata, follows the runtime workshop-checkpoint rules, and commits only the generated template path.

## Quality Rules

- The root node MUST be `type=composite`, `role=root`, and `executor=main`.
- `task` and `gate` are executable leaves; a gate MUST use `executor=main`.
- `composite` and `loop` MUST use `executor=main`.
- Every `subagent` leaf MUST include `instructions`, `deliverables`, and `acceptance`.
- A loop MUST define `loop.max_iterations` and `loop.on_limit`.
- A switch MUST define `switch.key` and mutually exclusive `role=case` or `role=default` children.
- Large documents and reports belong in artifacts; only short cross-node control values belong on the blackboard.
- Recognized control metadata MUST pass author validation before template generation and runtime validation after generation.

## References

- `assets/templates/flow-spec-template.json`: flow-spec example.
- `references/template-design-method.md`: workflow decomposition guidance.
- `references/template-package-contract.md`: template package contract.
- `references/migration-from-skill.md`: migration from prose-oriented Skills.
