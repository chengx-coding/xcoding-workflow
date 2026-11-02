---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: 20261102-1145-open-sandbox-xc-044
node_id: rt_work-order-20261102-1145-open-sandbox-xc-044__dyn-1__i1-world-engine
feature_ids: []
orchestration:
  tree_ref: .xcoding/work-orders/20261102-1145-open-sandbox-xc-044/runtime/orchestration.xml
---

# I1 implementation record — world engine

## Changed paths

- `js/config.js` — extended constants (product identity, 192×96 world, physics, day length, zoom,
  save key) while keeping every seed field the seed tests assert.
- `js/blocks.js` — new: 16 block definitions (hardness, tool class, harvest tier, drops, light,
  colours) and 11 item definitions (materials and three tool classes).
- `js/rng.js` — new: mulberry32 PRNG, FNV-1a string/int hashing, deterministic unit mapping.
- `js/noise.js` — new: seeded value noise (1D/2D) with fBm and smoothstep interpolation.
- `js/world.js` — extended: seed-compatible `createWorld` kept unchanged, new `generateWorld`
  (surface profile, biome bands, caves, ore veins, trees, flowers, clear spawn), terrain/surface
  height queries, RLE encode/decode and version-tolerant `serializeWorld`/`deserializeWorld`.
- `js/lighting.js` — new: flood-fill skylight and torch/block light, daylight curve, brightness.
- `js/time.js` — new: 4-minute clock, phase bands, daylight, formatted time, keyframed sky palette,
  sun/moon positions.
- `tests/worldgen.test.js`, `tests/lighting.test.js`, `tests/time.test.js` — new suites.

## Validation

- `node --test "tests/**/*.test.js"` → **27 tests, 27 pass, 0 fail** (144.7 ms). The six untouched
  seed tests remain in the run and still pass; 21 new assertions cover generation determinism,
  surface variety, caves/ores/trees/bedrock, ore depth, block-definition coverage, RLE round-trip and
  corruption rejection, sky/torch light, light opacity and day/night factors.
- `python tools/page_check.py` is not yet expected to pass end-to-end: the page still boots the seed
  shell until I3 rewires `index.html`; the static half of that check is unaffected by this slice.

## Notes and residual risk

- The legacy flat `createWorld` stays as a tested compatibility surface; the game calls
  `generateWorld`. This preserves the seed contract without weakening verification.
- Lighting is recomputed wholesale (18,432 tiles) on demand. Measured cost is deferred to the browser
  evidence stage; if it exceeds the frame budget, I3 debounces relight without changing semantics.
- World RLE payload is ~4.7 KB for a generated world versus ~36 KB for a raw JSON array.
- No external asset, network reference, dependency, or Git commit was introduced.
