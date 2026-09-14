# Template Package Contract

A workflow Skill should provide a small domain-owned package around the generic runtime:

```text
assets/
  orchestration-template.xml
references/
  runtime-usage.md
  subagent-contract.md
  artifact-contract.md
  blackboard-contract.md
```

The package may include domain-specific templates or scripts, but it must not copy the generic runtime state machine, viewer server, or XML parser.

## Template Requirements

- Generated and validated by `xc-orchestration-author`, then accepted by `xc-orchestration-runtime`.
- `schema_version="1"` and managed template access/integrity metadata.
- Template nodes use `template_id`, never runtime `id`.
- Root is `type=composite`, `role=root`, and `executor=main`.
- `task` and `gate` are leaves; gates use `executor=main`.
- `composite` and `loop` use `executor=main`.
- Subagent leaves declare instructions, deliverables, and acceptance.
- `switch` nodes declare a key and valid case/default children.
- Loop nodes declare a positive maximum iteration count and `loop.on_limit`.
- Dependencies use `depends_on_template="local:<template_id>"`.

## Control Metadata Requirements

The author recognizes `metadata.control_packet.*`, `metadata.completion.*`,
`metadata.gate.*`, `metadata.worker_profile.*`, and `metadata.delegation.*` in
flow specs. These prefixes fail closed: unknown recognized keys, invalid
owners, malformed compact canonical JSON, invalid selectors or names, and
incomplete paired declarations return `invalid_control_metadata` before
output is written. `details.violations` contains stable `{node,key,code}`
entries sorted by key, code, and node.

The recognized declarations are:

```text
metadata.control_packet.category.<category>.selectors
metadata.control_packet.category.<category>.min_sources
metadata.control_packet.category.<category>.artifact_min
metadata.control_packet.blackboard_keys
metadata.completion.required_fields
metadata.completion.artifacts.min
metadata.completion.artifacts.max
metadata.completion.artifacts.path
metadata.completion.checks
metadata.completion.check.<check>.subject
metadata.completion.check.<check>.facts.<field>
metadata.gate.outcomes
metadata.gate.decision_required
metadata.gate.outcome_key
metadata.worker_profile.schema_version
metadata.worker_profile.owner_skill
metadata.worker_profile.profile_id
metadata.worker_profile.security_mode
metadata.worker_profile.context_bindings
metadata.delegation.authorization
```

The `metadata.worker_profile.schema_version=1` member versions the runtime
assignment declaration. It is independent from the current-only Skill-local
profile source, whose root object has no `schema_version` field.

Control-packet categories require `selectors`, `min_sources`, and
`artifact_min`. Completion artifact bounds require both `min` and `max`; each
declared check requires a subject. Structured gates require outcomes and an
explicit `decision_required` value. Worker-profile metadata requires all five
members together on a task subagent leaf, and its bindings may reference only
that node's target contract, declared control categories, and selected
blackboard keys. Delegation authorization is a node-owned public grant ceiling,
not private Skill-profile content. Unknown ordinary `metadata.*` outside the
recognized prefixes remains compatible and is preserved.

Worker-profile and delegation violations additionally use
`unknown_worker_profile_metadata_key`, `missing_worker_profile_metadata_key`,
`worker_profile_metadata_too_large`,
`invalid_worker_profile_schema_version`,
`invalid_worker_profile_owner_skill`, `invalid_worker_profile_id`,
`invalid_worker_profile_security_mode`,
`invalid_worker_profile_context_bindings`,
`worker_profile_category_not_declared`,
`worker_profile_blackboard_key_not_declared`,
`unknown_delegation_metadata_key`, and
`invalid_delegation_authorization`. Existing control, completion, gate, and
owner violation codes remain unchanged.

The author and runtime own independent validators. Their acceptance and violation codes are checked against `tests/fixtures/orchestration/control-metadata-conformance-v1.json`; production code MUST NOT import or call the other Skill's private implementation.

## Integration Requirements

The domain Skill must document:

- Where `init` creates runtime trees.
- Which blackboard keys are shared and their allowed values.
- Artifact locations and ownership.
- The prompt contract for one delegated subagent node.
- User gate behavior and follow-up blackboard writes.

During execution, the domain Skill invokes runtime public commands; it does not inspect or mutate runtime XML directly.
