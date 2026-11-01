---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261101-2045-open-sandbox-xc-2"
node_id: "rt_work-order-20261101-2045-open-sandbox-xc-2__dyn-1__unit-and-static"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261101-2045-open-sandbox-xc-2/runtime/orchestration.xml"
---

# Verification — unit suites and static page contract

## Commands and outcomes

Environment: Node v24.13.1, Python 3.12.10, Windows, project root as the working directory.

1. `node --test "tests/**/*.test.js"` -> **41 tests, 41 pass, 0 fail** (`duration_ms` 247.4).
2. `python tools/page_check.py --screenshot .xcoding/.../tmp/verify-page.png` -> **`ok=true`**:
   static checks `ok=true` with an empty problem list, status marker pixel `[46, 204, 113]` distance
   0.0, canvas colour buckets 170.

## Suite coverage

| Suite | Cases | Evidence for |
| --- | ---: | --- |
| `tests/world.test.js` (seed, unchanged) | 6 | Config contract, world dimensions/seed, ground line, bounds, JSON round-trip, solidity |
| `tests/worldgen.test.js` | 7 | Determinism, column-10 anchor, surface/cave/ore/tree/water presence, bottom row and spawn safety, RLE codec |
| `tests/player.test.js` | 6 | Falling and landing, movement and wall stop, jump and land, coyote time, swimming, respawn |
| `tests/mining.test.js` | 5 | Hand rules, pickaxe tiers and speed, reach, progress/reset/completion, unbreakable/empty |
| `tests/inventory.test.js` | 4 | Add/count/atomic remove, invalid quantities, hotbar bounds/cycling, tools/placeable |
| `tests/crafting.test.js` | 4 | Planks/sticks/torches, unique pickaxes and costs, atomic failure, cost reporting |
| `tests/lighting.test.js` | 4 | Sky light and ground stop, day/night phases, torch spread and darkness, crystal/water attenuation |
| `tests/save.test.js` | 5 | Snapshot round-trip, corruption rejection, memory storage, storage failure handling, range validation |

The seed test file is byte-identical to the seed contract used by this work order:
`tests/world.test.js` is 2412 bytes, SHA-256 prefix `da2fdcf9f9acd445`; it was never edited, and its six
cases pass unchanged.

## Capability evidence

- **C2** generated world: determinism, anchored surface, caves, coal/crystal, trees, water, bottom row
  and spawn tests; static page check proves the page loads.
- **C3** movement/collision: landing, wall stop, jump, coyote, swimming, respawn.
- **C4** mining rules: hand vs pickaxe gating, tier speed, reach, progress and completion.
- **C5** inventory/hotbar: atomic counts, slot bounds/cycling, selected placeable.
- **C6** placement model: placeable mapping and selected-item rules; the input-to-world placement is
  proven in the browser node.
- **C7** save model: round-trip, corruption rejection, unavailable storage, range validation; real
  reload persistence is proven in the browser node.
- **C9** crafting: all five recipes, uniqueness, atomicity and cost display data.
- **C10** lighting model: sky, time phase, torch, crystal and water attenuation.
- **C11** tool gating: wooden vs stone pickaxe on stone and crystal.
- **C1** offline/static: page check finds no external references and all local assets resolve.

## Gaps assigned to the browser verification node

- Real keyboard/mouse interaction, reload persistence, canvas pointer mapping, audio unlock/mute,
  day/night visual change, new-world flow, console cleanliness and zero remote requests are not
  provable from Node unit tests.
- Performance under the browser loop is not measured by unit tests; the browser run provides frame
  availability but no numeric FPS budget, which is recorded as a non-blocking observation.

## Conclusion

The focused unit and static verification passes completely, with the seed contract intact and every
simulation capability in the accepted matrix covered by at least one executable assertion. No gap in
this scope blocks the work order; browser-only claims are carried to the next verification node.
