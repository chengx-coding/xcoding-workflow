---
schema_version: 1
document_kind: node-artifact
content_language: "en"
audience: "internal"
work_order_id: "20261102-1550-open-sandbox-xc-047"
node_id: "rt_work-order-20261102-1550-open-sandbox-xc-047__dyn-1__impl-foundation"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261102-1550-open-sandbox-xc-047/runtime/orchestration.xml"
---

# Implementation record — foundation (world, blocks, random, light)

## Scope

The accepted foundation unit from `solution.md`: shared configuration, deterministic random helpers,
the block/item registry, seeded world generation with the RLE world codec, and the light model. No
presentation, input or simulation code was changed by this node.

## Changed paths

| Path | Change |
| --- | --- |
| `js/config.js` | Rewritten: 1152×648 view, 360×140 world, physics/clock/save constants, 17 block ids and 10 item ids; the seed contract fields (`tileSize`, `worldWidth`, `worldHeight`, `gravity`, `blocks.air`, `blocks.grass`, `saveKey`, `blockNames`) are preserved. |
| `js/rng.js` | New: seeded `mulberry32`, integer hashes, 1D/2D value noise and fBm used by world generation. |
| `js/blocks.js` | New: block/item registry with solidity, hardness, required pickaxe tier, drops, light emission, station tags, palettes for procedural rendering, and tool lookup helpers. |
| `js/world.js` | Rewritten: flat spawn plateau, hills, sand patches, caves, depth-banded coal/iron/ember veins, trees, RLE serialization with legacy payload support, exposure/placement rules, minimap sampling. Keeps `createWorld`/`getBlock`/`setBlock`/`isSolid`/`serializeWorld`/`deserializeWorld` and `world.data` as the seed contract requires. |
| `js/light.js` | New: day factor, night/dusk predicates, sky + torch breadth-first light grid over bounded regions. |
| `tests/worldgen.test.js` | New: 14 tests for determinism, terrain shape, trees, caves, ore bands, bottom row, RLE round-trip, legacy payloads, rejection, exposure, placement and minimap sampling. |
| `tests/blocks.test.js` | New: 9 tests for the registry, tier gating, break-speed ordering, drops, light/station tags, tools and inventory tool lookup. |
| `tests/light.test.js` | New: 5 tests for day factor, sky light, a closed-room shadow, torch propagation and bounds clamping. |
| `tests/world.test.js` | Unchanged; every seed assertion still passes. |

## Validation

```console
node --test "tests/**/*.test.js"
# tests 33, pass 33, fail 0, duration ~120 ms
```

Covered assertions: two worlds from one seed are byte-identical; different seeds differ; the spawn
plateau is exactly `floor(height*0.65)` for `x=0…48`; hills exist beyond it; trees, caves and all three
ore bands exist with ember confined to the deep band; the bottom row is stone; RLE round-trips the
whole grid and encodes smaller than the raw byte array; invalid runs are rejected; exposure requires
an air neighbour; placement requires an empty tile with solid support; stones/ores refuse to break
below their tool tier and break faster with better tools; sky light reaches the surface, a closed
room is dark, and a torch lights its chamber.

## Convention accounting

- Project bridge: classic UMD modules work under `require()` and in the browser; UTF-8 with LF only;
  no network reference, external library or font was introduced; temporary files stayed in
  `tmp/`; no project Git commit was made.
- C1/C2: none applied beyond the bridge (L1 record status `not-applicable`).
- C3 de-facto seed patterns followed: frozen shared config, UMD wrapper, `node:test` +
  `node:assert/strict`.
- Seed test file not weakened.

## Residual risk

- The generated world assumes a seed gives enough trees near spawn; the generator plants four fixed
  trees on the spawn plateau, so the first gather step is always reachable.
- Light propagation is intentionally two-dimensional and blocks propagation through solid tiles;
  this is a deliberate simplification recorded in `analysis.md`.
- No browser rendering exists yet, so visual acceptance is deferred to the experience and
  verification units.
