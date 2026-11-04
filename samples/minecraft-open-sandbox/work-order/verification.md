---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261104-1337-2d-sandbox-game"
node_id: "rt_work-order-20261104-1337-2d-sandbox-game__dyn-1__verification-product"
feature_ids: []
orchestration:
  tree_ref: "/work/.xcoding/work-orders/20261104-1337-2d-sandbox-game/runtime/orchestration.xml"
---

# Verification: Emberblock Product

## Environment and Scope

- **Scope:** `regression` for a create work order with no feature baseline. Product scope and output
  profile `visual` (with the proposed experience lens) were taken from the accepted solution.
- **Environment:** Node v24.22.2, Python 3.12.3, Google Chrome 157.0.8103.38, Linux container.
- **Chrome prerequisite:** `HOME` was set to a writable directory under the workbench `tmp/` because
  the restricted container cannot create Chrome's default profile directory.
- **No product changes were made by this verification node.** All product code was frozen before the
  commands below.
- **Execution order:** unit tests, seed page check, automated real-browser probe, then review of the
  captured visual/state evidence. The probe captures the title, help, play, pack, save, night, day,
  narrow, pointer-state, and corruption-recovery states.

## Executed Commands and Outcomes

### 1. Pure test suite

```console
node --test "tests/**/*.test.js"
```

**Result:** exit 0; 25 tests, 25 passed, 0 failed. Six seed tests and nineteen project tests cover
config compatibility, deterministic terrain, layers, caves, ores, trees, spawn, light, inventory
stacking/full refusal, hand/table/furnace recipes, iron progression, AABB movement/jump/wall
collision, fall damage, reach/overlap, save round-trip, corruption rejection, and RNG reproducibility.
Log: `tmp/verification-tests.log`.

### 2. Project seed check

```console
python tools/page_check.py --screenshot <workbench>/tmp/verification-page.png
```

**Result:** exit 0. Static references passed; required `game`, `status`, `hud`, and `hotbar` IDs
present; every local asset resolves; no network asset reference; ready-marker pixel `[46, 204, 113]`;
145 canvas colour buckets. JSON: `tmp/verification-page-check.json`; screenshot:
`tmp/verification-page.png` (960 × 600).

### 3. Real-browser product probe

```console
python tools/play_probe.py --page index.html --out <workbench>/tmp/verification-browser
```

**Result:** exit 0; `ok=true`; 34/34 checks passed; 10/10 real pointer clicks matched their
pointerdown/pointerup target at 110 ms dwell; render loop 60.7 fps; no external requests; no page
exceptions or error logs. JSON: `tmp/verification-browser.json`.

The probe's own report includes all check names and the pointer click log. The run covers: fresh
title with Play/Help, help open/close, Play, real keyboard movement, tree mining, tutorial completion,
pack open, enabled planks craft, real craft click, pack close, hotbar placement, real right-click
placement, manual save, reload-to-Continue, block and pack persistence, night, day, narrow viewport
title and inventory, 10/10 pointer clicks, network audit, and corrupt-save recovery.

### 4. Focused manual browser scenarios

Run through the same standard-library CDP harness, with screenshots or state assertions:

- **Tool gating:** mined grass/dirt, then attempted stone with no pickaxe; block remained and the UI
  showed "Stone needs a wooden pickaxe or better." Selected wood pickaxe then broke stone and gained
  cobblestone.
- **Pack transfers:** picked up a stack, moved it between hotbar and pack, right-click split, placed
  one in an empty slot, and closed the pack with a held stack returned safely.
- **Full-pack craft refusal:** filled all 36 slots with 64 wood each (2,304 total), opened the pack,
  and clicked the ready Planks recipe. The inline pack feedback read "Your inventory is full." and
  the total stayed 2,304 wood; no item was lost or duplicated.
- **Station progression:** placed a crafting table, crafted a wooden pickaxe, placed a furnace,
  smelted three iron ingots, and crafted an iron pickaxe. Station chips showed "in reach" while near.
- **Light:** placed a torch in a cave and observed local warm illumination; captured day, night, and
  cave/torch states (`artifacts/evidence/day.png`, `night.png`, `cave-torch.png`).
- **Death/respawn:** set health to one and fell from height; death overlay appeared with stats,
  Respawn returned to the meadow at full health with the pack retained, and reload showed a live
  saved world.
- **Reset guard:** from pause with a live world, New World opened confirmation; cancel returned to
  pause; confirm created a new random-seed world and began play.
- **Return to title:** pause → Back to Title saved and returned to title with Continue and a saved
  timestamp; Continue resumed the world.
- **Map toggle:** M hid and re-showed the surface minimap.
- **Corrupt storage:** invalid JSON in `emberblock.save.v1` booted a fresh title with a visible,
  readable warning instead of an exception.

## Visual / Experience Evidence

Evidence files are in `artifacts/evidence/`:

| State | Evidence | Assertion |
| --- | --- | --- |
| First-run title | `start.png` | Visible Play and How to Play; seed; offline claim; no saved world |
| First-run help | `help.png` | Full controls, first steps, and visible close/back controls at 960×600 |
| Play / day | `playing.png`, `day.png` | World, HUD, hearts, clock, coordinates, quests, hotbar, minimap |
| Night | `night.png` | Materially different sky/palette, stars, moon, darker scene |
| Cave / torch | `cave-torch.png` | Underground darkness plus local torch glow and visible stone edges |
| Pack & Crafting | `inventory.png` | Station chips, 36 slots, recipe status, locked/ready feedback, no toast occlusion |
| Narrow viewport | `narrow.png` | 480×700, title/pack fit without clipping; usable layout |
| Corrupt save | `corrupt-recovery.png` | Fresh title with visible recovery notice |
| Pointer state | `pointer-state.png` | A hotbar slot selected after the 10-click sequence |

**First-run affordance (must): PASS.** Fresh-state probe finds both a visible primary Play action and
a visible How to Play entry. The help panel is reachable from the title, HUD `?`, and pause Controls.

**Interaction truth (proposed): PASS.** 10/10 real pointer clicks at 110 ms dwell had identical
pointerdown/pointerup targets. The probe used CDP mouse input, not `element.click()`. Hotbar slots are
real buttons; a full-inventory craft refusal ("Your inventory is full.") and unavailable recipes show
visible reasons.

**Visual-state backdrop (must): PASS.** Day and night are materially different with coherent sky,
sun/moon, cloud, and light changes. Cave air uses a dark backdrop with visible surrounding stone
edges; a placed torch produces local illumination. The title overlay keeps the live world behind it.

**Responsive / no clipping (must): PASS.** At 960×600 the help back button ends at y≈568 and the
inventory panel stays within the viewport. At 480×700 the title card and inventory panel stay within
the width and the pack closes cleanly. Primary title/help/hotbar controls remain visible.

**Progression / orientation (should): PASS.** Wood → planks → table → wooden pickaxe → stone →
stone pickaxe → furnace → iron ingot → iron pickaxe was exercised; the minimap and coordinates
provide orientation. Particles, procedural audio dispatch, and quest completion are present.

## Capability Matrix Verification

| Capability | Priority | Executed evidence | Result |
| --- | --- | --- | --- |
| Offline launch, Play/Help | must | page_check, probe start/help, screenshots | PASS |
| Deterministic world, hills/caves/ores/trees | must | 25 unit tests + day/cave screenshots | PASS |
| Move, jump, collide | must | physics tests; probe movement; manual jump | PASS |
| Mine with reach/hardness/tier | must | probe mining; manual stone refusal + pickaxe break | PASS |
| Place/break and persist | must | probe placement/save/reload; manual slot/pack | PASS |
| Inventory, stacking, hotbar | must | unit tests; probe; manual drag/right/Shift-click | PASS |
| Crafting and station progression | must | unit tests; manual table/furnace/iron chain | PASS |
| Day/night, cave and torch light | must | unit light tests; day/night/cave-torch screenshots | PASS |
| Health, fall, death/respawn | must | physics tests; manual death/respawn; screenshot | PASS |
| Save/autosave/load/reset | must | probe save/reload; manual reset; corruption probe | PASS |
| HUD/help/pause/responsive | must | 960×600 + 480×700 screenshots; probe layout checks | PASS |
| Particles/audio/minimap/quests | should | visual particles, audio code paths, manual map toggle, quest screenshots | PASS with audio-quality gap below |

### Stateful journeys

| Journey | Before → after evidence | Result |
| --- | --- | --- |
| Fresh start | title → Play → interactive world, tutorial toast, save created | PASS |
| Persistence | planks placed → Ctrl+S → reload → Continue → block/pack restored | PASS |
| Corrupt save | invalid payload → fresh title + visible recovery notice, no exception | PASS |
| Refused mining | stone targeted with no pickaxe → block unchanged + explicit reason | PASS |
| Refused crafting | missing station/ingredient → locked row + reason; inventory unchanged | PASS |
| Empty inventory | empty pack/recipe rows show labels and missing-input text, no dead primary button | PASS |
| New-world reset | pause → confirm required → cancel keeps world → confirm starts new world | PASS |
| Death/respawn | lethal fall → overlay/stats → respawn at meadow, pack retained, save written | PASS |
| Responsive | 960×600 and 480×700 title/pack/help/hotbar remain usable | PASS |

## Gaps and Residual Risks

- **Audio quality (should-level, not programmatic):** WebAudio calls run without exceptions and the
  mute toggle updates state, but headless verification cannot judge subjective loudness/timbre.
  This is a recorded should-level gap; no acoustic defect was reported.
- **Fixed 16:9 scene scaling:** the 960×540 render is scaled to the viewport. At extremely tall
  portrait aspect ratios the scene proportions stretch even though the responsive HUD/panels remain
  usable. This is documented in `README.md`; the product is designed for landscape.
- **Storage availability:** if a browser disables local storage, the game warns and runs session-only;
  reload persistence cannot be guaranteed in that environment. This is a platform risk, not a code
  failure.
- **No feature baseline / prior inventory:** not applicable; none existed.
- **No must-capability gaps; no user-accepted risk is required to proceed.**

## Conclusion

The accepted capability matrix is verified on the declared visual surface with executed unit,
static/browser, real-input, persistence, refusal, recovery, reset, death, and responsive evidence.
The seed checks remain green, the final 25-test suite passes, all 34 browser checks pass, 10/10
pointer interactions are truthful, and the game performs no external network requests. Verification
may proceed to the result document.
