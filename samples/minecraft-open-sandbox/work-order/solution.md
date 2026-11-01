---
schema_version: 1
document_kind: work-order-solution
content_language: "en"
work_order_id: "20261101-2045-open-sandbox-xc-2"
feature_ids: []
orchestration:
  main_tree_ref: ".xcoding/work-orders/20261101-2045-open-sandbox-xc-2/runtime/orchestration.xml"
---

# Solution — a small complete 2D Minecraft

## Selected change

Task type: `create`. Minimality strength: none (a create task maximizes user value inside the prompt
and the accepted capability matrix). Chosen scope: the accepted matrix C1-C15 from `analysis.md`,
implemented as a small complete game rather than a demo. Release trigger: the accepted solution plus
passing verification; promotion happens through the work order result, not a version bump (the bridge
declares no version policy). Implementation boundary: files under `index.html`, `css/`, `js/`, `tests/`,
`tools/` and `README.md` in this project only. No server, no network, no external dependency, no Git
commit.

The capability matrix is accepted as written: every `must` (C1-C8) and every accepted `should`
(C9-C15) is in the implementation scope; no capability is deferred. Recorded non-goals S12-S18
(health/hunger/death, hostile mobs/combat, redstone, multiplayer, 3D, streaming worlds, flowing
liquids/farming/animals/villages/dimensions) stay out unless a later user request reopens them.

## Feature baseline impact

No features are associated (`has_features=false`), so there is no baseline to modify, no
reconciliation and no synchronization. The seed's six tests and the page check are retained and must
keep passing unchanged.

## Implementation and migration strategy

### Runtime shape

Plain classic scripts with the seed's UMD wrapper (CommonJS for `node:test`, browser global
otherwise) loaded in dependency order from `index.html`. No build, no modules over HTTP, no fetch.

| Module | Contract |
| --- | --- |
| `js/config.js` | Frozen constants, block definitions, recipes, colours, controls text data, save key |
| `js/world.js` | Seeded generation, bounded get/set, solidity, JSON round-trip (seed contract), RLE encode/decode for saves |
| `js/player.js` | Fixed-step AABB movement, collision, jump, spawn finding |
| `js/mining.js` | Reach, break time, tool gating, drops, progress accumulation |
| `js/inventory.js` | Item counts, nine hotbar slots, selection, add/remove |
| `js/crafting.js` | Recipe table, craftability, atomic craft |
| `js/lighting.js` | Per-tile light from sky exposure and torch/crystal sources |
| `js/save.js` | Versioned snapshot, validation, `localStorage` adapter with memory fallback |
| `js/audio.js` | Lazy WebAudio synthesis, mute, no assets |
| `js/input.js` | Keyboard/pointer state, canvas coordinate mapping, context-menu suppression |
| `js/render.js` | Pre-rendered tile textures, sky/time, parallax, water, player, particles, cracks, light overlay |
| `js/ui.js` | Hotbar DOM, HUD, help/pause/craft overlays, toasts, save status |
| `js/main.js` | Boot/load, fixed-step loop, interactions, autosave, `window.__sandbox` state surface |

`index.html` gains the overlay markup and keeps `#game`, `#hud`, `#hotbar`, `#status` mandatory ids.
`css/style.css` keeps the page shell, adds responsive canvas scaling, overlay and hotbar styling.

### World

192x96 tiles at 24 px. A seeded 32-bit PRNG drives a smooth 1D value-noise heightmap with an
amplitude ramp that is zero at the left edge, so column 10 remains exactly at
`floor(height * 0.65)` and the seed tests keep passing. Layers: grass, dirt band, stone; 2D cave
noise carves the stone while leaving the top three sub-surface rows intact at column 10; coal and
crystal veins are placed by depth with a seeded distribution; trees and static lakes are added after
terrain; the bottom row is `stone` and is unbreakable by rule. Spawn is chosen on a safe surface tile
near the centre, with at least one tree within a short walk so the first Minecraft action is
reachable.

### Interaction and progression

Primary (left) hold mines within 5.5 tiles with a visible crack progression; secondary (right) places
the selected hotbar block into a reachable empty tile that does not intersect the player. Drops:
grass->dirt, stone->stone, wood->wood, leaves->leaves, sand->sand, coal ore->coal, crystal ore->crystal,
torch->torch. Hand can break organic/soft blocks; a wooden pickaxe unlocks stone and coal; a stone
pickaxe unlocks crystal and is faster on stone/coal. Torches and crystal blocks emit light.

Recipes: 1 wood -> 4 planks; 2 planks -> 4 sticks; 1 stick + 1 coal -> 4 torches; 3 planks + 2 sticks
-> wooden pickaxe; 3 stone + 2 sticks -> stone pickaxe. Tools have no durability; the crafting overlay
shows costs, eligibility and current counts.

Day length 240 s with dawn/day/dusk/night interpolation; the light map is recomputed on world edits and
on quantized time buckets, using sky light (15 by day, 4 by night) plus torch 14 / crystal 12
sources propagated with -1 per tile. Rendering draws tiles from pre-rendered textures, a time-tinted
sky with sun/moon/stars, parallax clouds, animated water, the blocky avatar with walk and arm-swing
animation, break/place particles and the per-tile darkness overlay.

### Persistence

`localStorage` key `small-minecraft-save-v1`, version 1. Snapshot: seed, dimensions, RLE world, player
position, inventory counts, hotbar order and selection, time ticks and day. Autosave every 8 s when
dirty, plus pause/save, page hide and before unload. Loading validates the version, dimensions, block
ids and inventory; any failure falls back to a fresh world and reports it, never a broken page. Every
storage access is wrapped; if storage is unavailable the game continues with an in-memory save and a
visible warning. New world requires confirmation from the pause menu.

### Documentation and controls

`README.md` documents the run method, the full controls table, saving, the world/mechanics summary and
the exact verification commands. The same controls are listed in the in-game help overlay, opened with
`H` and from the pause menu.

## Verification strategy

1. **Seed suite unchanged**: `node --test "tests/**/*.test.js"` keeps all six original world tests.
2. **New unit suites** for generation invariants (including the column-10 anchor and bottom-row stone),
   physics/collision, mining rules and drops, inventory, crafting, lighting, and save round-trip plus
   corruption recovery.
3. **Static/page check**: `python tools/page_check.py` proves the shell, local assets, no network
   references, the green status marker and a non-blank canvas.
4. **Interactive browser check** (`tools/browser_check.mjs`, Node built-ins only): launches headless
   Chrome with a temporary profile over the DevTools Protocol, asserts a clean boot and no network
   requests, dispatches real key events to move and jump, real mouse events to mine a block and place
   it, opens help and crafting with real keys, saves through the pause menu, reloads the page and
   proves the edit, inventory and position survived, captures day and night screenshots, and fails on
   any console exception or failed assertion.
5. **Acceptance mapping**: C1-C7 and C9-C13 have direct unit or browser evidence; C8 and C15 have
   content/viewport assertions; C14 is reviewed from captured screenshots; the quality contract is
   checked against the same evidence, with any gap recorded in the final result.
