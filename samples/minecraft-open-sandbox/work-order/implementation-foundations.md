---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261104-1337-2d-sandbox-game"
node_id: "rt_work-order-20261104-1337-2d-sandbox-game__dyn-1__implement-foundations"
feature_ids: []
orchestration:
  tree_ref: "/work/.xcoding/work-orders/20261104-1337-2d-sandbox-game/runtime/orchestration.xml"
---

# Implementation: Foundations

## Scope

Implemented the pure, testable foundations for Emberblock: block/item/recipe registries, seeded noise,
world generation and lighting, inventory/crafting, player physics, and versioned save encoding.

## Changed Paths

- `js/config.js` — extended block registry, item metadata, recipes, stations, and tuning constants.
- `js/rng.js` — FNV seed hashing, mulberry32, value noise, and fractional Brownian motion.
- `js/world.js` — 320 × 144 terrain, caves, ores, trees, decoration, safe spawn, sky/torch light,
  bounded block API, diff/apply changes, full serialization compatibility.
- `js/inventory.js` — stack merging, counts, removal, full-inventory refusal, nearby stations,
  recipe status, transactional crafting.
- `js/physics.js` — AABB tile collision, coyote jump, acceleration/sprint, fall distance, damage,
  healing, respawn, reach and overlap helpers.
- `js/save.js` — save schema, diff encoding, strict validation, corruption errors, apply/load helpers,
  storage wrappers.
- `tests/foundations.test.js` — 18 focused tests across these modules.

The seed's `js/world.js` API names and the seed's six tests remain compatible.

## Evidence

- `node --test "tests/**/*.test.js"` — 24/24 passing (6 seed + 18 foundation).
- Deterministic seed check: repeated `createWorld` calls produce byte-identical data and spawn.
- Terrain checks confirm grass/dirt/stone layering, caves, coal, iron, trees, decoration, and safe
  spawn.
- Light checks confirm sky reaches the surface and a deep cave cell is dark; a torch begins at 14 and
  attenuates locally.
- Inventory checks confirm stack limits, tools as single stacks, full-pack refusal, hand/table
  recipe gating, and progression tiers.
- Physics checks confirm landing, jumping, wall collision, fall damage threshold, reach, overlap,
  damage, healing, and respawn.
- Save checks confirm diff round-trip, inventory/player/time restoration, and rejection of malformed
  JSON, bad coordinates, unknown blocks, and unknown items.

## Convention Accounting

- **C1 project bridge:** English, UTF-8/LF, vanilla JavaScript, no library/CDN/font/network imports,
  no project commit, seed checks preserved. All followed.
- **L1 discovery record:** no additional C1/C2 files beyond the bridge; no conflict or ambiguity.
- **Line endings:** authored files are UTF-8 with LF.
- **No feature baseline:** no prior inventory, no baseline change.

## Residual Risk

The browser renderer, UI, audio, input loop, and persistence wiring are the next implementation unit.
The pure modules are ready for that integration; the seed tests pass.
