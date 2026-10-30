---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-0000-minecraft-sandbox"
node_id: "rt_work-order-20261030-0000-minecraft-sandbox__dyn-1__impl-world-generation"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261030-0000-minecraft-sandbox\\runtime\\orchestration.xml"
---

# Implementation — world generation and time

## Scope

Approved implementation unit U1 (seeded world generation) plus the day/night clock module. The accepted
solution matrix maps M1 to this unit and M13 to `js/daynight.js`; the clock landed in this
world-and-time slice as an implementation-order choice, which does not change the approved scope or
matrix.

## Changed paths

- `project/js/config.js` — added the numeric default seed, the nine-block registry (grass, dirt,
  stone, sand, wood, leaves, planks, cobblestone, glass), hotbar order, starter stock, per-material
  hardness, day-cycle length, save/settings keys and the save schema version; kept every existing
  seed-contract field.
- `project/js/rng.js` (new) — FNV-1a string hashing, uint32 seed normalisation, user seed parsing
  with actionable failures, mulberry32 PRNG, range/int/pick helpers and a stable per-cell hash.
- `project/js/world.js` — rewritten generator on top of the seed contract: sine-mix height field with
  a flat spawn plateau, sand valleys, grass/dirt/stone strata, cave pockets below the surface, seeded
  trees, spawn search over clear terrain columns, surface map, and the unchanged bounded
  access/serialization API.
- `project/js/daynight.js` (new) — normalised clock, advance/wrap, palette interpolation for sky
  colours and light, phase/label helpers, celestial positions and night tint.
- `project/tests/rng.test.js`, `project/tests/generation.test.js`, `project/tests/daynight.test.js`
  (new) — focused coverage for the unit. The seed test file `project/tests/world.test.js` is
  unchanged.

## Validation

```console
node --test tests/world.test.js tests/rng.test.js tests/generation.test.js tests/daynight.test.js
```

Result: 35 tests, 35 pass, 0 fail (log: `tmp/impl-world-tests.log`). The untouched seed suite remains
green, including the ground-line contract at column 10 and the serialization round-trip.

Confirmed world facts for the default seed: grass, dirt, stone, sand, wood and leaves are all
present; more than 100 cave air cells exist below the surface; the bedrock floor is solid; the spawn
search lands on a terrain block with two clear cells above.

## Convention accounting

- C1 bridge — English code/comments: followed. Two-space indentation and the existing UMD module
  wrapper: followed. UTF-8/LF: followed. No formatter or linter exists: no formatting churn applied.
- C1 bridge — modules loadable in Node: followed; every new module uses the same UMD wrapper and
  requires no DOM at load time.
- C1 bridge — no network references: followed; no network or external asset string exists in these
  files.
- C1 bridge — do not delete or weaken seed tests: followed; the file is untouched and passing.
- Project constraint — no project commit: followed; no Git action taken.
- No C2 configured signal applies (no `.editorconfig`, formatter, linter or CI workflow).

## Residual risk

- The flat spawn plateau is a deliberate generation constraint that keeps the seed contract and the
  first moments of play safe; hill variety starts just east of it. A future request that wants hills
  at the origin would need a coordinated seed-test change.
- Cave density is tuned by one threshold; it produces explorable pockets without undermining the
  surface, and the visual review stage checks the result in the rendered page.
