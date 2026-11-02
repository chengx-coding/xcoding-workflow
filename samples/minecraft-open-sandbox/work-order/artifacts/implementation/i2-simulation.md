---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: 20261102-1145-open-sandbox-xc-044
node_id: rt_work-order-20261102-1145-open-sandbox-xc-044__dyn-1__i2-simulation
feature_ids: []
orchestration:
  tree_ref: .xcoding/work-orders/20261102-1145-open-sandbox-xc-044/runtime/orchestration.xml
---

# I2 implementation record — simulation and progression

## Changed paths

- `js/inventory.js` — new: item counts, nine-slot hotbar with automatic assignment, removal that
  frees slots, best-tool resolution, serialization.
- `js/physics.js` — new: AABB tile collision, acceleration/friction, coyote time and jump buffering,
  single-tile ledge climbing, landing impact, fall-damage curve, settle-out-of-ground recovery.
- `js/mining.js` — new: harvest rules by tool class and tier, hardness/time computation, hold-to-mine
  progress with target reset, instant break with correct drops and "tool too weak" reason, reach.
- `js/placement.js` — new: placement rules (empty hand, bounds, occupied tile, reach, player overlap,
  support for torches/flowers), consuming placement.
- `js/crafting.js` — new: 11 recipes with progressive unlocks, affordability, consumption/production,
  visible recipe states.
- `js/tasks.js` — new: eight-step task chain, progress notes, one-shot completion, rewards, progress
  serialization.
- `js/backdrop.js` — new: edit history with before/after labels, bounded buffers, undo/redo stacks,
  edit/mode/time/view pulses, readable descriptions.
- `js/save.js` — new: versioned save envelope, validation, storage adapter with memory fallback and
  surfaced failure, load/save game helpers.
- Tests: `tests/physics.test.js`, `tests/inventory.test.js`, `tests/mining.test.js`,
  `tests/placement.test.js`, `tests/crafting.test.js`, `tests/tasks.test.js`,
  `tests/backdrop.test.js`, `tests/save.test.js`.

## Validation

- `node --test "tests/**/*.test.js"` → **79 tests, 79 pass, 0 fail** (212 ms). Seed tests still pass.
- Coverage highlights: jump height and landing, wall blocking, ledge climb, fall-damage threshold,
  tool-tier harvest matrix, progress reset on retarget, placement rejection reasons, recipe locks
  and consumption, one-shot task rewards, undo/redo and bounded backdrops, save round-trip and
  forced storage failure.

## Notes and residual risk

- Jump speed was raised to 16.4 tiles/s (2.5-tile jump) after the first focused run showed the
  initial 14.2 value only cleared 1.8 tiles; the change is in `js/config.js` and covered by the jump
  test.
- Task rewards are applied by the caller so `tasks.js` stays a pure progress record; the UI/I3 slice
  wires rewards into the inventory.
- `save.js` keeps the world as an RLE payload inside the envelope; a corrupt payload is reported as
  `{error}` rather than thrown, so the boot path can fall back to a new world.
- No external asset, network reference, dependency, or Git commit was introduced.
