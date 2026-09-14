# Adapter Capability Statement Contract

A statement is a canonical `xc-delegation-adapter-capabilities/v1` object with exactly `schema_version`, `kind`, `adapter_id`, `adapter_version`, `mode`, `evidence`, and `capabilities`.

Each capability declares `id`, `support`, and `values`. `support` is `enforced`, `validated-only`, or `unsupported`. `values` is either the exact supported atoms or the single adapter-only wildcard `*`. The adapter-wide mode bounds every individual capability: an `enforced` statement cannot contain a weaker capability and an `unsupported` statement cannot contain a stronger one.

## Structured Enforcement Evidence

`evidence` is a sorted array of zero or more `xc-delegation-adapter-evidence/v1` objects. Each object has exactly:

```text
schema_version = 1
kind = "xc-delegation-adapter-evidence/v1"
adapter_version = exact adapter_version from the containing statement
coverage = one v1 coverage identifier
artifact = safe NFC POSIX-relative evidence-artifact identifier
sha256 = lowercase SHA-256 of the reviewed evidence bytes
```

The v1 coverage identifiers are `allow`, `bypass`, `deny`, `path-isolation`, `secret-visibility`, and `terminal-binding-visibility`. The array is sorted and unique by `coverage`. Unknown evidence versions, fields, coverage identifiers, mismatched adapter versions, unsafe artifact identifiers, and malformed digests fail closed.

An `enforced` claim additionally requires a pinned version containing a concrete numeric component and no placeholder token such as `unverified`, `unknown`, `latest`, `current`, `fixture`, or `dev`. It must declare every v1 capability as `enforced` and contain exactly one evidence record for every v1 coverage identifier. Empty or partial evidence and mixed capability support cannot authorize enforcement. `validated-only` and `unsupported` statements may keep `evidence=[]`; this preserves honest statements when fixed-version host evidence does not exist.

The structured records bind reviewed evidence bytes to one exact adapter version; they do not authenticate the publisher or prove that the evidence is truthful. Release review still owns provenance and authenticity. Schema acceptance, prompt conformance, generated configuration, and local compiler tests establish validation behavior only. They do not establish host enforcement.

Statements are immutable inputs to a prepared envelope and receipt through their canonical digest. Changing a statement requires a new reviewed Bundle and normal setup/update/rollback handling. Preparation never discovers mutable host state or silently substitutes a different adapter.

The executable semantic validator is shared by source Bundle construction, installed-Bundle setup and planning, doctor readiness, direct adapter loading, and authoritative preparation. An adapter statement rejected at one of these boundaries is invalid at all of them.
