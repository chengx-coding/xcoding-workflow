---
schema_version: 1
document_kind: work-order-solution
content_language: en
work_order_id: 20261104-1337-2d-sandbox-game
feature_ids: []
orchestration:
  main_tree_ref: /work/.xcoding/work-orders/20261104-1337-2d-sandbox-game/runtime/orchestration.xml
---

# Work Order Solution: Emberblock

## Selected Solution and Scope Decision

**Task type:** create. **Minimality presumption:** none. **Chosen scope:** one coherent vanilla
browser game with a finite 320×144 side-view tile world, a DOM HUD/overlay layer, procedural canvas
art, generated audio, and local persistence. No prior feature baseline or capability inventory
exists, so no preservation disposition applies.

The solution delivers the analysis capability map in one implementation boundary:

- **World:** deterministic terrain with hills, dirt/stone strata, winding caves, coal/iron deposits,
  trees, ground cover, bedrock, safe spawn, and a compact surface minimap.
- **Player:** acceleration-based running, sprint, coyote-time jump, AABB tile collision, fall damage,
  health, death and respawn at spawn with inventory retained.
- **Sandbox verbs:** held-pointer mining with reach and hardness; tool tier gates for stone and ores;
  block drops to a stackable inventory; right-click placement with collision/overlap checks; torch
  support and local light; particles and procedural sound for feedback.
- **Progression:** hand recipes (planks, sticks, crafting table, torches), table recipes (wooden and
  stone pickaxes, furnace, stone bricks), furnace recipes (iron ingot, glass). Stations must be within
  six tiles and placed in the world. This is a small, legible wood → stone → iron arc.
- **Persistence:** autosave plus manual save; a versioned payload stores the seed and a block diff
  rather than the full world; player, inventory, hotbar selection, health, time, stats, settings, and
  tutorial state also persist. Corrupt data falls back safely; unavailable storage falls back to
  memory with a visible notice.
- **Interface:** first-run start screen with Play/Continue, New World, and How to Play; in-game quest
  strip; hearts/clock/coordinates/save state; sound and help buttons; inventory/crafting overlay;
  pause and death overlays; minimap toggle; documented keyboard and mouse controls.
- **Visual identity:** "Emberblock" — warm, illustrated pixel blocks, layered parallax hills, a moving
  sun/moon and stars, animated torch flame and embers, soft light gradients, and a dusk palette. All
  art and audio are generated in-browser; no external assets.

**Scope decision:** release when the capability matrix below passes. **Explicit boundary:** no mobs,
combat, hunger, redstone, multiplayer, infinite chunk streaming, or additional dimensions. These are
unrequested pocket-scope boundaries, not user-forbidden features. **Version disposition:** the project
bridge defines no version policy; the internal game/save schema is `1` and the visible build string is
`1.0.0`. No release asset or package version changes are proposed.

## Capability Matrix and Baseline Impact

| Capability | Implementation | Verification |
| --- | --- | --- |
| Offline launch, Play/Help | `index.html`, `css/style.css`, `js/ui.js`, `js/main.js`; no external refs | `page_check.py`, static scan, CDP load and 10-click pointer probe |
| Generated block world | `js/rng.js`, `js/world.js`; seeded noise, caves, ores, trees, decor, spawn | Node determinism/layer/cave/spawn tests; screenshot |
| Move, jump, collide | `js/physics.js`; AABB sweep, gravity, coyote jump, sprint | Physics unit tests; CDP key movement before/after |
| Mine with reach/hardness/tier | `js/config.js`, `js/main.js`, `js/render.js`; progress and refusal feedback | Mining/tier/reach tests; CDP hold, assert block/inventory/toast |
| Place/break persistence | `js/world.js`, `js/save.js`, `js/main.js`; diff and reload | Save round-trip tests; CDP place, autosave, reload |
| Inventory/hotbar | `js/inventory.js`, `js/ui.js`; stack limits, drag/swap, selected slot | Inventory unit tests; CDP slot interactions |
| Crafting progression | `js/config.js` recipes, `js/inventory.js`, `js/ui.js`; station proximity | Recipe/station tests; CDP craft sequence |
| Day/night, cave/torch light | `js/world.js` light field, `js/render.js` overlay, `js/main.js` clock | Light unit tests; day/night/cave screenshots |
| Health/fall/respawn | `js/physics.js`, `js/main.js`, `js/ui.js` | Damage tests; CDP forced fall/death/respawn |
| Save/autosave/reset | `js/save.js`, `js/main.js`, `js/ui.js`; confirmed reset | Save/corruption tests; CDP reload and cancel/confirm reset |
| HUD/help/responsive | `index.html`, `css/style.css`, `js/ui.js`; safe-area layout, 480px rules | DOM rect probes at 960×600 and 480×700; screenshots |
| Particles/audio/minimap/quests (should) | `js/textures.js`, `js/audio.js`, `js/render.js`, `js/ui.js`, `js/main.js` | Screenshot/dynamic state checks; mute toggle; manual audio check |

No existing public contract changes; `config.js` block IDs are extended while retaining the seed's
`air`, `grass`, `dirt`, `stone`, `wood`, and `leaves` properties and world API names. Seed consumers
continue to work.

## Implementation and Migration Strategy

1. **Pure foundations.** Extend `config.js` with block/item/recipe registries and tuning values;
   add `rng.js` (seed hash, mulberry32, value noise/fBm) and `world.js` (generation, block API,
   light field, spawn, diff apply, serialization). Add `inventory.js` (stacks, add/remove/merge,
   recipe availability and craft), `physics.js` (AABB collision and movement), and `save.js`
   (versioned payload encode/decode, diff, corruption validation).
2. **Browser presentation.** Add `textures.js` (deterministic 24×24 tile variants, tool/item icons,
   sky/parallax drawing helpers), `audio.js` (WebAudio synth effects and mute), `render.js` (sky,
   parallax, tiles, cave backdrop, light map, player, particles, torch glow, minimap), and `ui.js`
   (start/help/pause/inventory/death dialogs, hotbar, quests, HUD, drag transfers, toasts).
3. **Composition.** Rewrite `main.js` as the state machine and game loop: boot/load, fixed-step
   movement, camera follow, mouse target/mining, placement, interaction, save scheduling, keyboard
   input, overlay coordination, and error reporting. Keep `#game`, `#status`, `#hud`, and `#hotbar`
   IDs for the seed page check.
4. **Presentation and documentation.** Rewrite `index.html` and `css/style.css` for the full layout;
   rewrite `README.md` with description, launch, controls, systems, save behavior, architecture, and
   verification. Controls are also available in-game from the first screen and pause menu.
5. **Tests and probes.** Keep and adapt the seed tests; add focused pure-module tests for generation,
   inventory/crafting, physics, light, and save. Add a `tools/play_probe.py` standard-library CDP
   harness for real browser interaction and screenshots. Run both seed commands plus the new tests.

Save compatibility/migration: version `1` is the initial format. Decode validates version, dimensions,
seed, coordinates, block IDs, stack counts, finite numbers, and time bounds. Future versions can
migrate at decode; unknown/corrupt payloads produce a clean new world with a notice, never a crash.
The original seed's `serializeWorld` full-data API remains for tests.

## Verification Strategy

- **Pure evidence:** `node --test "tests/**/*.test.js"` for world determinism/layers/caves/spawn;
  block solidity/tier/hardness; inventory stack/merge/full/removal; recipe station/ingredient rules;
  collision, jump, fall distance/damage; diff save round-trip and corruption rejection; light decay.
- **Seed surface:** `python tools/page_check.py` must stay green: required IDs, no external refs,
  ready status pixel, colour-rich canvas.
- **Visual/experience evidence:** fresh-start screenshot; start/help/inventory screenshots; day,
  night, and underground screenshots; 960×600 and 480×700 layout probes; 10/10 real pointer clicks at
  ≥90 ms on primary controls with matching down/up target.
- **Stateful probes (CDP):** Play starts input; movement and jump change position; mine a surface block
  and place it; autosave/reload restores state; corrupt save recovers; New World cancel/confirm;
  refused mining without correct pickaxe; refused tool craft without table; close overlays with Escape.
- **Manual review:** visual coherence, no clipping/occlusion, readable contrast, sound feedback, pause
  and death flows, and absence of console errors/network requests.
- **Profile handoff:** implementation inherits the convention record (English, UTF-8/LF, no build or
  network) and verification inherits `visual` plus experience checks. No report group is mounted
  (`work_order.requires_report=false`, `user_waived`).
