# Verification Staleness Tracking

Pure file-based tracking of which verification surfaces were verified at which milestone. The tracker records per-file hashes; later nodes recompute them to find stale surfaces before re-verifying. It is a derived view: it records what verification claimed, never what the tests themselves proved.

## Activation

Enabled for multi-milestone work orders and for work orders whose surfaces are expected to drift between verification passes. The planner activates it through the bridge or planning policy; it MUST NOT be activated ad hoc by a single node.

## Policy

- Mark at each milestone verification. After a verification node passes, record the verified file set with `mark` using the milestone timestamp. Scope keys by milestone and surface so later queries answer "what changed since this milestone".
- Query before re-verification. Re-verifying an unchanged surface is wasted effort; `query` first and target only keys reported as `stale` or `unknown`. A clean `current` result may justify skipping re-verification when policy allows.
- Full regression at milestone boundaries. Milestone seals run the complete declared regression scope regardless of staleness. Staleness tracking narrows interim passes, never milestone acceptance.
- Replace, never edit, a record. Content changed since the last mark requires a new mark with a new key or `--replace`; there is no partial update.
- Derived view, never authoritative. A `current` result proves nothing about test outcomes. Actual test runs remain the only source of verification truth; the tracker only says which files a previous run covered and whether they moved since.
- Single writer per store. Concurrent marks against one store are unsupported; scope one store per work order, milestone, or session as the plan declares.

## Command Surface

- `verification_staleness.py mark --store P --key K --verified-at TS --files f1,f2,... [--replace]`
- `verification_staleness.py query --store P [--keys K1,K2]`
- `verification_staleness.py remove --store P --key K`

`query` reports `stale` entries with per-file `changed` or `missing` status, `current` entries with their `verified_at`, and `unknown` keys. All output is deterministically sorted. All failures report `ok:false` with a stable error code and exit 0.
