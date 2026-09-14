# Capability Policy

## Vocabulary

v1 uses exactly ten identifiers:

1. `project.read.declared`
2. `project.write.owned`
3. `workbench.read.declared`
4. `workbench.write.artifact`
5. `workbench.write.tmp`
6. `process.exec.named`
7. `network.outbound.allowlisted`
8. `secret.use.named`
9. `skill.invoke.declared`
10. `runtime.terminal.assigned-node`

Capability values are explicit allowlist atoms. Path capabilities use safe project- or workbench-relative POSIX paths. Terminal values are `block`, `complete`, or `fail`. Network values are lowercase hosts with an optional port. No prefix, glob, inherited environment, ambient credential, or implicit command interpretation is added. `*` is reserved for fixed adapter capability statements and never accepted in a profile or policy.

## Six Layers

The result for each requested capability is:

```text
profile request
  intersect XC v1 ceiling
  intersect project ceiling
  intersect node authorization
  intersect caller narrowing
  intersect host support at the selected security mode
```

Node authorization must already be a subset of the profile request and project ceiling. Caller constraints must be a subset of node authorization. Violating either relationship is `unsafe_capability_widening`, even if a later set intersection would remove the excess.

A required capability with no effective value blocks the complete preparation. An optional capability may be omitted; the envelope records its stable reason and per-layer provenance. Failure order and capability output are sorted by capability ID.

## Security Modes

- `enforced`: the adapter statement itself and the individual capability must both be `enforced`.
- `validated-only`: a `validated-only` or `enforced` individual capability is accepted, but the result makes no host-enforcement claim.
- `unsupported`: the capability is unavailable and blocks when required.
- `legacy-prompt`: an explicit compatibility route for nodes without a v1 profile. It is never a fallback from a failed v1 preparation.

The repository's initial third-party host statements are `validated-only`; network and secret capabilities are `unsupported`. Presence of a field, generated Agent file, prompt instruction, or local validator is not enforcement evidence.

## Output and Terminal Coupling

Every declared artifact path must appear in the effective `workbench.write.artifact` values. Allowed terminal operations are the intersection of effective `runtime.terminal.assigned-node` values and runtime-authorized terminal operations. A dispatch-authoritative preparation requires this intersection to be non-empty; a diagnostic envelope may expose an empty result but remains non-authoritative.

Every `required_skills` entry must also appear in the effective `skill.invoke.declared` values before authoritative dispatch. An optional Skill capability may be omitted only when no omitted value is named by `required_skills`. Diagnostic compilation may expose the contradiction for inspection, but it never turns that result into dispatch authority.

The runtime owns the one-shot terminal authority; no bearer or general mutation selector enters the envelope or receipt.
