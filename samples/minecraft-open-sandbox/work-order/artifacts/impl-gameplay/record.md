---
schema_version: 1
document_kind: node-artifact
content_language: "en"
audience: "internal"
work_order_id: "20261102-1550-open-sandbox-xc-047"
node_id: "rt_work-order-20261102-1550-open-sandbox-xc-047__dyn-1__impl-gameplay"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261102-1550-open-sandbox-xc-047/runtime/orchestration.xml"
---

# Implementation record — simulation (player, inventory, crafting, progression, hollows, save)

## Scope

The accepted simulation unit from `solution.md`. It turns the world and block model into playable
rules: movement, inventory, crafting stations, the eight-stage goal chain, the night threat, and the
persistent save envelope. Presentation and browser wiring are the next unit.

## Changed paths

| Path | Change |
| --- | --- |
| `js/player.js` | Rewritten: AABB collision against the tile grid, walk acceleration/friction, jump with coyote time, jump buffer and variable height, reach/distance helpers, health, invulnerability, regeneration, damage, death, respawn, save/restore. |
| `js/inventory.js` | New: 36 slots with a 9-slot hotbar, 99-item stacks, non-stacking tools, add/remove/count/has, swap with merge, wrapped hotbar selection, serialization with unknown-id rejection. |
| `js/crafting.js` | New: 15 recipes across hand/workbench/furnace, station proximity scanning in the world, availability reasons (`station` vs `materials`) with missing-item detail, and a craft operation that consumes inputs and stores outputs. |
| `js/progression.js` | New: the eight-stage goal chain, persistent counters, ordered stage advancement, current/hint/summary projection, and serialization. |
| `js/mobs.js` | New: night-only hollows limited to three, terrain-aware spawning away from the player in darkness, chase/wander movement with tile collision and hopping, contact damage on a cooldown, attack hit-testing, damage/death, daylight despawn. |
| `js/save.js` | New: versioned localStorage envelope with RLE world, validation (schema, world, player, inventory, progress), safe read/write/clear, corrupt and quota handling, summaries and duration/age formatting. |
| `tests/player.test.js` | New: 9 tests for physics, collision, jump, reach, damage, respawn and saved state. |
| `tests/inventory.test.js` | New: 10 tests for stacking, tools, removal, has, swap/merge, selection, full inventory and serialization. |
| `tests/crafting.test.js` | New: 8 tests for the recipe table, hand/workbench/furnace rules, missing materials, station range and the beacon chain. |
| `tests/progression.test.js` | New: 7 tests for ordering, the full chain, counters, serialization and corrupt data. |
| `tests/mobs.test.js` | New: 7 tests for spawning, light gating, despawn, contact cooldown, attack/death and the population limit. |
| `tests/save.test.js` | New: 6 tests for the envelope, round-trip, summaries, clearing, corruption and storage failures. |

## Validation

```console
node --test "tests/**/*.test.js"
# tests 80, pass 80, fail 0, duration ~172 ms
```

Key assertions: the player lands on the spawn plateau, collides with a wall and can jump; damage
respects invulnerability and respawn restores health; tools never stack and a full inventory returns
the leftover; the wooden pickaxe cannot be crafted without a workbench and the iron chain requires a
furnace; the beacon consumes all three refined materials and a failed craft consumes nothing;
progression cannot skip stages and completes all eight when the conditions are met; hollows spawn
only at night in darkness, damage once per cooldown and respect the population limit; a save/load
round-trip preserves world edits, inventory, progress and clock, while corrupt or unavailable storage
returns a structured error.

## Convention accounting

- Project bridge: UMD modules requireable under Node and loadable from `file://`; UTF-8/LF; no
  external dependency or network reference; temporary scripts stayed in `tmp/`; no project Git
  commit; the seed test file untouched.
- C1/C2: none beyond the bridge.
- C3 de-facto seed patterns followed (frozen config, UMD, `node:test`).
- All new behaviour is dependency-injected where it helps testing (storage, context objects).

## Residual risk

- Mob behaviour uses `Math.random` only for wandering, which keeps gameplay lively but means mob
  positions are not deterministic; they are intentionally not part of the save.
- The save format is version 1 and rejects unknown schemas; a future format change needs a deliberate
  migration step.
- No rendering or DOM exists yet, so these rules have not been exercised through the browser; the
  next unit wires them and the verification unit proves the real-pointer path.
