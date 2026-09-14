# Worker Profile Contract

## Ownership and Resolution

A private worker profile has exactly one canonical location:

```text
skills/<owner-skill>/assets/workers/<profile-id>/profile.json
```

Callers supply the owning Skill root and `profile_id`. They never pass the profile file path. `owner_skill` must equal the root directory name and `profile_id` must equal the requested logical identifier. Each `instruction_resources` entry remains below that same profile directory. Portable paths also reject NTFS alternate-stream colons, Windows reserved device names, and trailing dot or space aliases. Resolution rejects symlinks, junctions, every detected reparse point, path collisions, identity changes during a read, and paths that escape after physical resolution.

## Current Profile Shape

The root has exactly these fields: `profile_id`, `owner_skill`, `description`, `instruction_resources`, `required_skills`, `capability_vocabulary`, `capabilities`, `context`, `outputs`, `delegation`, `failure_policy`, and `compatibility`. Skill-local profile source is current-only and intentionally carries no root `schema_version`; Git history records source evolution.

Arrays that represent sets are sorted and unique. Paths use NFC forward-slash relative syntax. Capabilities contain exact `id`, `requirement`, and non-empty `values` fields. Context bindings contain `id` and `required`. Output artifacts contain `id`, `path`, and `required`.

The profile JSON Schema rejects all structurally representable invalid paths, identifiers, capability values, and fixed-policy values. The executable validator remains authoritative for UTF-8 byte limits, NFC normalization, sorted-by-identifier ordering, case-folded or normalization collisions, owner-directory matching, and other cross-field rules that Draft 2020-12 JSON Schema cannot express exactly. Producers must pass both schema validation and the public executable validator; schema acceptance alone is never dispatch authority.

These values are fixed for the current profile contract:

```json
{"compatibility":{"legacy_fallback":false,"on_unsupported":"block"},"delegation":{"allowed":false,"max_depth":0},"failure_policy":{"on_invalid_input":"block","on_required_capability":"block","silent_fallback":false}}
```

Host, model, sandbox, permission, runtime tree, node, gate, retry, loop, project topology, and project command fields are not profile fields. Unknown fields fail validation. A profile containing the retired root `schema_version` is rejected as an unknown field; validators do not dual-accept or silently migrate it.

## Structured Data Limits

- One JSON input: 64 KiB.
- Nesting: 32 levels.
- Aggregate JSON values: 4,096 nodes.
- One string: 16 KiB UTF-8.
- One instruction resource: 16 KiB; aggregate instruction resources: 64 KiB.
- Profile instruction resources: 16; required Skills: 32; context bindings: 64; output artifacts: 32.

Canonical JSON uses sorted object keys, compact separators, UTF-8, and one trailing LF. A BOM, duplicate key, non-finite number, non-NFC string, or non-canonical byte representation fails closed.

## Dynamic Overlay

An overlay is `xc-worker-profile-overlay/v1` and binds `work_order_id`, `node_id`, and `attempt`, plus a UTC expiry. It may shorten the description only to a literal prefix, remove optional capabilities, remove optional context and outputs, and lower the context byte limit. It cannot replace instructions, remove required context or output, change capability values, add a Skill or resource, or enable delegation.

The envelope contains the overlay digest and cleanup requirement, never the host path. The trusted host gateway retains the path, removes only the same validated digest after terminal handling, and treats mismatch, residue, or deletion failure as recovery evidence.

## Promotion Rule

A profile remains Skill-private when only its owning Skill uses it. Promote the role to a persistent canonical Agent when multiple Skills share it, users select it directly, or it requires a distinct persistent model or permission identity.
