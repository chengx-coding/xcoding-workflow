---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261101-2045-open-sandbox-xc-2"
node_id: "rt_work-order-20261101-2045-open-sandbox-xc-2__dyn-1__core-simulation"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261101-2045-open-sandbox-xc-2/runtime/orchestration.xml"
---

# Core simulation implementation

## Changed paths

- `js/config.js` — rewritten: full block/item/tool/recipe/control/palette configuration, 192x96 world,
  day length, save identity.
- `js/world.js` — rewritten: seeded terrain with amplitude ramp, caves and shafts, coal/crystal ores,
  static lakes and beaches, trees, safe spawn with a starter tree, bounded access, JSON round-trip and
  RLE codec.
- `js/player.js` — rewritten: fixed-step AABB movement, per-axis collision, jump buffer and coyote
  time, swimming, respawn.
- `js/mining.js` — new: reach, tool gating, break times, drops, progressive mining.
- `js/inventory.js` — new: counts, atomic add/remove, hotbar selection/cycling, tools, placeable
  selection.
- `js/crafting.js` — new: recipe lookup, affordability, atomic craft, cost reporting.
- `js/lighting.js` — new: sky/torch/crystal light BFS, day-phase sky level, darkness mapping.
- `js/save.js` — new: versioned snapshot, RLE encode/decode, validation, `localStorage` adapter with
  memory fallback.
- `tests/worldgen.test.js`, `tests/player.test.js`, `tests/mining.test.js`, `tests/inventory.test.js`,
  `tests/crafting.test.js`, `tests/lighting.test.js`, `tests/save.test.js` — new suites.
- `tests/world.test.js` — unchanged on purpose (seed contract).

## Validation

Command: `node --test "tests/**/*.test.js"` from the project root.

Result: 41 tests, 41 pass, 0 fail. That includes the six original seed tests, untouched, and 35 new
cases covering generation determinism and the column-10 anchor, cave/ore/tree/water presence, bottom
row, RLE, physics landing/walls/jump/coyote/swimming, mining tiers/reach/progress, inventory
atomicity, crafting costs/uniqueness, lighting day/night/torch/water attenuation, and save
round-trip/corruption/storage failure.

## Capability coverage in this unit

- C2 generated world: covered by generation tests and the seed contract.
- C3 movement and collision: covered by the physics suites.
- C4 mining rules: covered for reach, hardness, tool tiers and drops.
- C5 inventory/hotbar model: covered for counts, selection and tools.
- C6 placement model: `placeableSelected` and `placeable` mapping covered.
- C7 save model: snapshot, RLE, validation and fallback covered.
- C9 crafting: covered.
- C10 lighting model: covered.
- C11 pickaxe gating: covered.
- C1, C8, C12-C15 are presentation/shell/verification concerns handled by later nodes.

## Convention accounting

- English source and comments: followed.
- UTF-8/LF: every file written as LF; the module UMD style and two-space indentation follow the
  seed's de-facto C3 pattern.
- No external dependency or network reference: followed; the modules are dependency-free and use
  only local `require`/globals.
- Seed tests not weakened: followed; `tests/world.test.js` is byte-for-byte unchanged and passes.
- Temporary files under the work order `tmp/`: followed.
- No project Git commit: no commit created.

## Residual risk

- `file://` `localStorage` is not exercised by Node; the browser check must prove it.
- The light BFS cost on edits is acceptable in unit runs but still needs browser frame-time evidence.
- The player resting-contact probe is heuristic; the browser check should confirm stable walking,
  jumping and placement on the real surface.
