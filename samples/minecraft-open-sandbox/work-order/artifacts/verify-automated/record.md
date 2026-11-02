---
schema_version: 1
document_kind: node-artifact
content_language: "en"
audience: "internal"
work_order_id: "20261102-1550-open-sandbox-xc-047"
node_id: "rt_work-order-20261102-1550-open-sandbox-xc-047__dyn-1__verify-automated"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261102-1550-open-sandbox-xc-047/runtime/orchestration.xml"
---

# Verification record - automated project checks

## Environment

Node.js v24.13.1, Python 3.12.10, Chrome installed at
`C:\Program Files\Google\Chrome\Application\chrome.exe`. Commands run from the project root
(`C:\dev\xcoding-workflow-dev\wf-iterations\open-sample-047\xc\project`). No network is required.

## Commands and outcomes

| Command | Result |
| --- | --- |
| `node --test "tests/**/*.test.js"` | exit 0; 80 tests, 80 pass, 0 fail, 0 skipped; 177.8 ms. |
| `python tools/page_check.py --screenshot <workbench>/artifacts/screens/09-page-check.png` | exit 0; `ok=true`; static `problems=[]`; status marker pixel `[46,204,113]`, distance 0.0; canvas 148 colour buckets (threshold 12). |

Assertion coverage (10 test files, all executed):

| Test file | Behaviour proved |
| --- | --- |
| `tests/world.test.js` (seed, unchanged) | Config contract, world dimensions/seed, ground line and sky, bounded access, serialization round-trip, solidity. |
| `tests/worldgen.test.js` | Determinism per seed, different seeds differ, flat spawn plateau at `floor(height*0.65)` including `x=10`, hills, trees, caves, depth-banded coal/iron/ember with ember deep-only, stone bottom row, RLE round-trip and payload rejection, exposure and placement rules, minimap sampling. |
| `tests/blocks.test.js` | Registry completeness, tier gating (stone/iron/ember), faster breaks with better tools, drop chain, torch/beacon light and station tags, tool types, inventory tool lookup, item naming. |
| `tests/light.test.js` | Day factor and night/dusk predicates, sky light at surface vs deep, enclosed room darkness, torch propagation, bounds clamping and day/night transfer. |
| `tests/player.test.js` | Player size/health, gravity landing, wall collision, jump and landing, reach, tile overlap, damage/invulnerability/death, respawn, saved state. |
| `tests/inventory.test.js` | 36 slots, stacking and overflow, non-stacking tools, removal, count/has, swap and merge, wrapped selection, full-inventory leftover, serialization and unknown-id rejection. |
| `tests/crafting.test.js` | 15-recipe table, hand recipes, workbench requirement, missing-material detail, furnace smelting, station range, beacon chain, no consumption on failure. |
| `tests/progression.test.js` | Ordered stages, full eight-stage completion, mining/placing/crafting counters, serialization, corrupt-data fallback. |
| `tests/mobs.test.js` | Night spawn on dark ground, daylight despawn, light-blocked spawn, contact damage cooldown, attack/kill/remove, population limit, ground spawn under tree canopy. |
| `tests/save.test.js` | Versioned envelope, world/inventory/progress/clock round-trip, size bound, summaries and formatting, clear, corrupt rejection, quota/storage failure surfacing. |

Page check details: all required ids `game`, `status`, `hud`, `hotbar` exist; every served file is
local (no `http(s)://`, `//cdn` or remote `@import`); the fixed status dot is exactly the ready green;
the canvas contains 148 sampled colour buckets. The retained capture is
`artifacts/screens/09-page-check.png`.

## Capability mapping

| Capability | Evidence |
| --- | --- |
| C1 offline boot, no external asset | page_check static (no external reference) + headless boot with ready marker |
| C3 movement and collision | player tests (landing, wall, jump) |
| C4 mining rules | blocks/world tests (tier gate, break time, exposure, reach); real pointer proof is in `verify-browser` |
| C5 placement rules | world placement tests + browser placement proof |
| C6 inventory/hotbar | inventory tests |
| C7 crafting stations | crafting tests |
| C8 tool tiers and ore gating | blocks/world tests |
| C9 world generation | worldgen tests (determinism, caves, ores, trees, seed invariants) |
| C10/C11 light and clock | light tests |
| C12 survival | player/mobs tests |
| C13 goal chain | progression tests |
| C14 save/load | save/player/inventory/progression tests; browser reload proof in `verify-browser` |
| C15 orientation | world minimap sampling tests; visual capture in `verify-browser` |
| C16/C17 art and audio | page-check capture; visual evidence and runtime mute path in `verify-browser`; audio is procedural by code review |
| C18 controls documentation | README and in-game help reviewed; help panel captured in `verify-browser` |

## Gaps and unexecuted checks

- No automated check proves audio output quality; the code review and the runtime unmuted/muted path
  cover only the mechanism.
- Visual art direction is judged from captured screenshots, not from a rendering-difference test.
- Touch/mobile layout is outside the accepted target and is not tested.
- Save schema migration for a future version 2 is not tested because there is no version 2.
- The browser-level interaction, persistence and first-run evidence belongs to `verify-browser` and
  is not duplicated here.

## Conclusion

Both project bridge commands pass from the project root, the seed test file is unchanged, and the
behaviour asserted above is the behaviour the accepted capability matrix requires. The remaining
browser-only acceptance is delegated to the sibling browser verification node.
