# Dispatch Input Contracts

All documents below are canonical strict JSON objects. Unknown fields are invalid.

## Node Packet

`xc-delegation-node-packet/v1` has exactly:

```text
schema_version = 1
kind = "xc-delegation-node-packet/v1"
work_order_id = canonical managed work-order ID
node_id = canonical runtime node ID
attempt = positive integer
status = "running"
executor = "subagent"
authorization = {"capabilities": GRANT_ARRAY}
context = object keyed by declared profile context binding ID
allowed_terminal_operations = sorted unique subset of ["block", "complete", "fail"]
```

Each grant has exactly `id` and sorted unique non-empty `values`. The runtime assignment wrapper MUST expose this object as its `node_packet` member without adding runtime-owned fields.

## Node Profile Reference

`xc-node-worker-profile-ref/v1` has exactly:

```text
schema_version = 1
kind = "xc-node-worker-profile-ref/v1"
owner_skill = xc-* slug
profile_id = slug
security_mode = "enforced" | "validated-only"
context_bindings = binding source object by declared binding ID
```

A binding source is exactly one of:

- `{"source":"target-contract"}`
- `{"category":"CATEGORY","source":"control-packet"}`
- `{"key":"SELECTED_SCALAR_KEY","source":"blackboard"}`

`legacy-prompt` is not a profile security mode. A legacy node omits the v1 profile declaration and uses its explicit legacy route.

The runtime assignment wrapper MUST expose this object as its `node_profile_ref` member without adding runtime-owned fields. Separate wrapper members may carry target contract, scoped control packet, terminal operations, and deterministic assignment digests.

## Policies

The project policy is exactly:

```json
{"grants":[],"kind":"xc-project-delegation-policy/v1","schema_version":1}
```

The caller constraints object is exactly:

```json
{"grants":[],"kind":"xc-delegation-caller-constraints/v1","schema_version":1}
```

Each grant uses the same exact `id` and `values` shape as node authorization. Node authorization must be within both the profile request and project ceiling. Caller constraints must be within node authorization. A wider targeted input fails with `unsafe_capability_widening`; it is not silently intersected into apparent success.

## Resolved Profile

`resolve-profile` returns a `resolved_profile` member whose value is exactly `xc-resolved-worker-profile/v1` with:

- validated `profile`;
- `base_profile_sha256` and `resolved_profile_sha256`;
- ordered `resources`, each with `path`, raw-content `sha256`, and UTF-8 `content`;
- `overlay`, either null or exact digest, expiry, target, and cleanup requirement.

`compile-envelope` accepts that member as its `--resolved-profile-json` document. The command is diagnostic and always writes `dispatch_authoritative=false`.

## Runtime Integration Rule

The runtime validates only the tool-neutral profile reference and node-local binding shape. It does not locate or parse a Skill-private profile. The trusted main or host gateway feeds the assignment wrapper's strict members into `prepare`. A pending, main-executor, gate, terminal, stale-attempt, mismatched-profile, or non-running node cannot produce a valid node packet.

`prepare` also applies dispatch-readiness checks after the six-layer capability intersection. It rejects a result unless at least one effective `runtime.terminal.assigned-node` value overlaps `allowed_terminal_operations`, and it rejects any `required_skills` value absent from the effective `skill.invoke.declared` grant. `compile-envelope` may retain these empty or contradictory results for diagnostics because its envelope is always non-authoritative.
