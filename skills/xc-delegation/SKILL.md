---
name: "xc-delegation"
description: "Validates and prepares Skill-local worker profiles for one assigned managed-workflow node. Invoke when a Skill delegates a private role through xc-delegated-agent and needs strict owner resolution, capability narrowing, a deterministic envelope, or read-only legacy discovery."
---

# XC Delegation

`xc-delegation` is the public boundary between a Skill-owned private worker role and the persistent `xc-delegated-agent` host. The owning Skill keeps its profile at `assets/workers/<profile-id>/profile.json`; callers pass the owning Skill root and logical profile ID, never an arbitrary profile path.

## Parameters

- `skill_root` - `path`; required
  - Scope: Absolute root of the owning `xc-*` Skill.
- `profile_id` - `string`; required
  - Scope: Lowercase logical identifier resolved only below the owning Skill's `assets/workers/` directory.
- `node_packet_json` - `path`; required for compilation or preparation
  - Scope: Canonical `xc-delegation-node-packet/v1` input for one running subagent attempt.
- `node_profile_ref_json` - `path`; required for compilation or preparation
  - Scope: Canonical `xc-node-worker-profile-ref/v1` reference emitted by the runtime assignment boundary.
- `project_policy_json` - `path`; required for compilation or preparation
  - Scope: Canonical project capability ceiling.
- `caller_constraints_json` - `path`; required for compilation or preparation
  - Scope: Canonical final caller narrowing.
- `adapter_id` - `string`; required for preparation
  - Scope: Versioned statement under this Skill's `assets/adapters/` directory.
- `dynamic_overlay` - `path`; optional
  - Scope: Main-session-created, node-and-attempt-bound narrowing overlay. It never adds instructions, resources, Skills, capabilities, context, outputs, network, secrets, or delegation.

## Operations

Validate or inspect a profile without authorizing dispatch:

```text
xcoding delegate validate-profile --skill-root ROOT --profile-id ID --json
xcoding delegate resolve-profile --skill-root ROOT --profile-id ID [--dynamic-overlay FILE] --json
```

Compile a deterministic diagnostic envelope from canonical inputs:

```text
xcoding delegate compile-envelope --resolved-profile-json FILE --node-packet-json FILE --node-profile-ref-json FILE --project-policy-json FILE --adapter-capabilities-json FILE --caller-constraints-json FILE --out FILE --json
```

Prepare one dispatch-authoritative envelope atomically:

```text
xcoding delegate prepare --skill-root ROOT --profile-id ID --node-packet-json FILE --node-profile-ref-json FILE --project-policy-json FILE --adapter-id ID --caller-constraints-json FILE [--dynamic-overlay FILE] --out FILE --json
```

Discover legacy producers without mutation or prompt disclosure:

```text
xcoding delegate scan-legacy --source-root ROOT --json
```

Only `prepare` may return `dispatch_authoritative=true`. Validation, resolution, and diagnostic compilation never establish permission to dispatch. Authoritative preparation additionally requires a non-empty effective assigned-node terminal overlap and effective Skill grants for every `required_skills` entry. An invalid, expired, unsupported, denied, stale, mismatched, or operationally incomplete v1 input blocks; it never falls back to the legacy prompt path.

## Required Method

1. Read [profile-contract.md](references/profile-contract.md) before authoring or changing a profile.
2. Read [dispatch-inputs.md](references/dispatch-inputs.md) before integrating a runtime assignment packet or calling `prepare`.
3. Read [capability-policy.md](references/capability-policy.md) before selecting required versus optional capabilities or a security mode.
4. Read [adapter-contract.md](references/adapter-contract.md) before adding or changing a host statement.
5. Validate the profile, obtain a running-attempt assignment wrapper through the runtime public interface, and call `prepare` with its exact `node_packet` and `node_profile_ref` members.
6. Dispatch only the canonical envelope written by a successful `prepare` call. Treat the receipt as integrity and audit linkage, not publisher authentication or execution attestation.
7. When a dynamic overlay was used, arrange terminal-path cleanup with the trusted host gateway. Cleanup failure or residue is a visible recovery condition.

For trusted same-process integrations, use `TrustedDelegationGateway` from the
installed `xcoding.delegation` package. `prepare_dispatch` retains the exact
overlay and artifact bindings outside the worker envelope, issues the runtime's
single-use terminal capability, and returns a process-local `GatewaySession`.
Call `consume(session, request)` after the worker returns; it delegates the
terminal transition to `TerminalBroker`, emits a detached receipt on success,
and attempts identity-pinned overlay cleanup in a `finally` path for every
authenticated outcome or rejection. Cleanup failures return recovery evidence
and are never hidden. `abort(session)` is the explicit cleanup path when a
worker never reaches terminal consumption. The gateway is not a daemon or a
cross-process transport, and its session/capability objects MUST NOT be
serialized or placed in the worker-visible envelope.

## Constraints

- v1 profiles MUST set `delegation.allowed=false`, `max_depth=0`, block required denials, and disable silent and legacy fallback.
- Effective capabilities are the parameter intersection of profile request, XC ceiling, project ceiling, node authorization, caller narrowing, and host support for the selected security mode.
- `enforced`, `validated-only`, and `legacy-prompt` are distinct. No host or capability may be labeled `enforced` without a pinned non-placeholder adapter version and complete structured allow, deny, bypass, path-isolation, secret-visibility, and terminal-binding-visibility evidence.
- Profile resources use safe NFC POSIX-relative paths inside the profile directory. Absolute, drive, UNC, backslash, dot-segment, NTFS alternate-stream, reserved-device, trailing-dot-or-space, link, junction, generic reparse, collision, changed-during-read, and digest-mismatched inputs fail closed.
- Structured inputs are bounded canonical UTF-8 JSON without a BOM, duplicate keys, non-finite numbers, non-NFC strings, unknown fields, or unknown major versions.
- Network access, secrets, and broad write scopes are absent by default and require explicit agreement at every applicable layer.
- The runtime owns node state and terminal authority. This Skill does not parse orchestration state, expose bearer material, or provide a worker mutation CLI.
- Profile-local workers are private implementation details. Roles shared across Skills, directly user-selectable, or requiring a distinct persistent model or permission identity belong in `agents-src/agents/`.

## Resources

- [profile-contract.md](references/profile-contract.md) - exact profile, overlay, resource, and promotion rules.
- [dispatch-inputs.md](references/dispatch-inputs.md) - exact node packet, profile reference, policy, and resolved-profile contracts.
- [capability-policy.md](references/capability-policy.md) - capability vocabulary and six-layer no-widening semantics.
- [adapter-contract.md](references/adapter-contract.md) - host evidence modes and adapter statement rules.
- [migration.md](references/migration.md) - read-only legacy discovery and explicit migration method.
- `assets/schemas/` - normative JSON Schema companions for the profile, overlay, and envelope. The executable validators remain authoritative for bounded-byte, canonical-order, Unicode-normalization, collision, and cross-field rules that JSON Schema cannot express exactly.
- `assets/workers/read-only-evidence/` - neutral authoring and test fixture, not a persistent selectable Agent.
