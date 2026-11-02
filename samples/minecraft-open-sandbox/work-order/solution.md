---
schema_version: 1
document_kind: work-order-solution
content_language: "en"
work_order_id: "20261102-1550-open-sandbox-xc-047"
feature_ids: []
orchestration:
  main_tree_ref: ".xcoding/work-orders/20261102-1550-open-sandbox-xc-047/runtime/orchestration.xml"
---

# Solution — Emberdeep, a small Minecraft-like 2D sandbox

## Scope decision

- **Task type**: `create`.
- **Minimality strength**: none. A create task maximizes user value inside the constraints and the
  quality contract instead of minimizing the change.
- **Chosen scope**: Option A from `analysis.md` — a side-view block sandbox with mining and placing,
  crafting and station progression, four material tiers, torch lighting and a day/night cycle, a
  light survival layer, a deterministic world with caves and depth-banded ores, an eight-stage goal
  chain ending in the Ember Beacon, persistent saving, orientation UI and a coherent presentation.
- **Not chosen**: the top-down variant (discards the seed's gravity/camera frame) and the minimal
  gather-and-build demo (rejected by the goal's loop-depth acceptance condition).
- **Release/promotion triggers**: none. This work order delivers the product in the repository; it
  does not publish, deploy or promote an environment.
- **User confirmation reference**: the delegated request to run the full managed lifecycle; no
  further human decision is outstanding. The solution approval gate records the decision.
- **Version disposition**: the project bridge declares no version policy, so no project release
  version is assessed or changed. The in-game version label is product content, not a release bump.
- **Implementation boundary**: the product files in the repository root (`index.html`, `css/`,
  `js/`, `tests/`, `tools/`, `README.md`) plus this workbench's own artifacts. No `.xcoding/features`
  directory is created, no project Git commit is made, and no network or external asset is added.

## Accepted capability matrix

Every `must` and `should` row is mapped to an implementation unit and a verification. Non-goals are
inherited from `analysis.md` (multiplayer, NPCs/villages, redstone, enchanting, dimensions, bosses,
hunger/farming, durability, fluid simulation, creative flight) and are not part of the accepted
matrix.

| # | Capability | Priority | Implementation unit | Verification |
| --- | --- | --- | --- | --- |
| C1 | Offline boot from `index.html`, no build, no external asset/network | must | `index.html`, `css/`, classic scripts, `tools/page_check.py` compliance | `page_check.py` static + headless runtime checks; browser boot check |
| C2 | First-run affordance and onboarding | must | `ui.js` title overlay, hints, help; `index.html` shell | Browser: title visible, real-pointer start, hint after start, screenshots |
| C3 | Movement, gravity, solid collision, camera | must | `player.js`, `main.js` | Unit tests for collision/step; browser movement/key evidence |
| C4 | Real-pointer mining with hardness, tier gate, drops | must | `input.js`, `main.js` mining loop, `blocks.js`, `player.js` reach | CDP pointer harness 10/10 hold ≥90 ms; unit tests for gating/hardness |
| C5 | Block placement from hotbar | must | `input.js`, `main.js`, `world.js` placement rules | Unit tests for placement rules; browser right-click placement evidence |
| C6 | Inventory, hotbar, counts, slot moves | must | `inventory.js`, `ui.js` | Unit tests for add/remove/stack/move; HUD screenshot |
| C7 | Crafting with hand/workbench/furnace stations | must | `crafting.js`, `ui.js` | Unit tests for every recipe and station proximity; browser craft evidence |
| C8 | Tool tiers gate stone/iron/ember; tiers speed mining | must | `blocks.js`, `crafting.js`, `main.js` | Unit tests for requirement and speed tables; browser progression evidence |
| C9 | Deterministic world with hills, forests, sand, caves, ore bands | must | `rng.js`, `world.js` | Unit tests for determinism, caves, ore bands, trees, seed invariants |
| C10 | Skylight, darkness, torches | must | `light.js`, `render.js`, `main.js` | Unit tests for light function; day/night and lit/unlit screenshots |
| C11 | Day/night cycle, backdrop state | must | `main.js` clock, `render.js` sky, `light.js` | Unit tests for clock/light factor; screenshots at day and night |
| C12 | Health, damage, respawn, night threat | should | `mobs.js`, `player.js`, `ui.js` | Unit tests for damage cooldown/death; browser night-state evidence |
| C13 | Eight-stage goal chain with persistent stage | must | `progression.js`, `ui.js`, `main.js` | Unit tests for every stage transition; save round-trip |
| C14 | Save/load/continue with truthful display | must | `save.js`, `ui.js`, `main.js` | Unit tests for RLE codec and save validation; browser reload evidence |
| C15 | Minimap, coordinates, depth, compass | must | `ui.js` minimap, `render.js` map sampling | Unit tests for map sampling; screenshot |
| C16 | Art direction and state-responsive backdrop | must | `render.js`, `css/style.css`, generated textures | Screenshots day/night/underground/title; visual inspection |
| C17 | Procedural audio feedback | should | `audio.js` | Code review of WebAudio-only generation; muted/unmuted browser state |
| C18 | Controls in game and README | must | `ui.js` help/pause, `README.md` | Review of both surfaces; screenshot of help panel |
| C19 | Tests and browser interaction evidence | must | `tests/*.test.js`, `tools/page_check.py`, `tools/browser_check.js` | The commands themselves plus recorded evidence artifacts |

## Product architecture

All source is dependency-free classic JavaScript that also loads under Node's `require()` for tests
(UMD wrapper, as the seed does). Load order in `index.html`:

```text
config -> rng -> blocks -> world -> light -> player -> inventory -> crafting
       -> progression -> mobs -> save -> audio -> render -> ui -> input -> main
```

| Module | Responsibility |
| --- | --- |
| `config.js` | Frozen constants: view/world size, physics, reach, clock, save key/version, block and item ids. |
| `rng.js` | Deterministic PRNG, value noise, hash helpers (seedable, testable). |
| `blocks.js` | Block/item registry: names, solidity, hardness, required tool tier, drops, light emission, palette, tool metadata. |
| `world.js` | Seeded generation (surface profile, spawn plateau, hills, sand, trees, caves, ore bands), block access, placement validity, RLE serialize/deserialize, minimap sampling. |
| `light.js` | Sky + torch light grid over a visible region, day factor, `lightAt`. |
| `player.js` | AABB physics and collision, jump/coyote time, reach, health/damage timers, spawn/respawn. |
| `inventory.js` | 36 slots, 9-slot hotbar, stacking, add/remove/count, selection, slot swap, serialization. |
| `crafting.js` | Recipe table with station requirements, station proximity from the world, availability reasons, craft execution. |
| `progression.js` | Eight-stage chain, completion checks over persistent stats, events for new stages. |
| `mobs.js` | Night-time hollows: spawn/despawn rules, chase, contact damage, damage/death, transient serialization. |
| `save.js` | Versioned save envelope, RLE world, safe localStorage read/write/remove, metadata formatting. |
| `render.js` | Procedural tile textures, parallax sky, sun/moon/stars, entities, breaking cracks, particles, light composite, HUD-adjacent canvas effects. |
| `ui.js` | DOM overlays (title/onboarding, inventory + crafting, pause, help, death, victory), HUD (hearts, clock, quest, coords/depth, save state), hotbar, minimap, toasts. |
| `input.js` | Keyboard/mouse state, pointer→world mapping, hold-mining, placement, hotbar keys/wheel, UI routing. |
| `audio.js` | Procedural WebAudio effects, mute state, unlock on first gesture. |
| `main.js` | Boot/load menu, fixed-step loop, interaction resolution, save orchestration, `window.__game` state and test hooks, status marker. |

## Interaction and controls specification

| Input | Action |
| --- | --- |
| `A` / `D`, `←` / `→` | Move left / right. |
| `Space` | Jump (variable height; coyote time before landing). |
| Hold left mouse | Mine the block under the pointer within reach; release cancels. If the pointer is over a hostile within range, the same button attacks it. |
| Right mouse | Place the selected hotbar block into a valid empty tile. |
| `1` … `9`, mouse wheel | Select a hotbar slot. |
| `E` | Open/close inventory and crafting. |
| `Esc` | Pause menu (resume, save, help, new world, mute). |
| `H` | Help/controls. |
| `M` | Mute or unmute procedural audio. |

Mining rules: the target must be within 5.5 tiles of the player, must be a non-air block, must touch
at least one air tile (so digging must proceed from an exposed face), must be breakable with the
current best tool tier, and accumulates progress while the pointer stays on the same tile. Breaking
adds the drop to the inventory. Placement requires an empty target tile, an adjacent non-air
support, no overlap with the player or a hostile, and an available item; it consumes one.

## World, clock, save and lighting model

- **World**: 360 × 140 tiles at 24 px. A flat spawn plateau at `y = floor(height*0.65)` spans
  `x = 0…44` (preserving the seed invariants at `x=10`), then hills grow outward; oak trees, sand
  patches, two-octave caves, and depth-banded coal/iron/ember veins; the bottom row stays stone.
- **Clock**: one day is 300 seconds. Time in `[0,1)`; sunrise at 0.0, noon 0.25, sunset 0.55, night
  0.6–0.95, dawn at 0.95. Daylight factor drives sky tint and skylight strength.
- **Light**: for the visible region plus a 24-tile margin, sky light starts at 15 on top-exposed air
  and decays with depth/shadow; torch light propagates breadth-first from torch blocks with a radius
  of 9 and decays one level per tile. The renderer composites a smooth dark overlay from the grid, so
  torches visibly light the cave and the surface darkens at night.
- **Save schema (version 1)**: `{schema, version, savedAt, seed, world:{width,height,rle}, player:{x,y,health},
  inventory:{slots,selected}, progress:{stage,stats,flags}, clock:{day,time}, stats:{blocksMined,playtime}}`.
  RLE is `[[blockId,count],...]`. Saves are written to `localStorage` under a versioned key, autosaved
  every 20 s and on pause/unload, and shown on the title screen as a Continue summary (day, blocks
  mined, playtime, saved time). Corrupt saves are rejected with an in-game notice and a fresh world
  offer; storage failures are surfaced, never silent.

## Verification strategy

1. **Logic tests** with `node --test "tests/**/*.test.js"` (seed test file untouched and passing):
   world determinism and seed invariants, seam/ore/cave/tree presence, RLE round-trip, placement and
   mining eligibility, tool gating and break times, player collision/jump/reach, inventory, every
   recipe with station proximity, every progression stage, mob damage/death, light grid and day
   factor, clock, save validation/migration.
2. **Page check** `python tools/page_check.py` from the project root: required elements, no external
   reference, ready status marker, non-blank canvas (screenshot retained for the record).
3. **Browser interaction evidence** via `tools/browser_check.js`, a dependency-free Node program that
   drives the installed Chrome over the DevTools protocol:
   - boot with no console error and `__game.ready`;
   - first-run affordance visible and dismissed by a real dispatched pointer click;
   - ten mining trials: compute an exposed, reachable block, dispatch `Input.dispatchMouseEvent`
     press at its screen position, hold 350 ms, release, and verify the block became air and the
     inventory increased; require 10/10;
   - negative control: `document.querySelector('#game').click()` must not break a block;
   - placement: right-click a valid tile and verify the block and inventory delta;
   - persistence: save through the real pause menu, reload the page, verify the Continue summary,
     continue, and verify the mined block and inventory survived; verify the save indicator text;
   - day/night/underground/inventory screenshots as visual evidence.
   The harness writes a JSON result and screenshots into the work order's `artifacts/` directory.
4. **Capability evidence map**: every `must` and `should` capability is mapped to a command outcome,
   test assertion group, or screenshot in the verification artifact and the result document.

## Risks and rollback

The seed files were copied to the work order `tmp/seed-baseline/` before implementation. The
repository has no commit history, so that copy is the rollback source for any file that must be
restored. Risks identified in `analysis.md` (seed invariants, storage availability, pointer-test
determinism, lighting cost, canvas mapping) are carried with the same mitigations; the
pointer-harness design in this solution is the direct answer to the interaction-truth requirement.
No unresolved material decision remains, and no capability is deferred.
