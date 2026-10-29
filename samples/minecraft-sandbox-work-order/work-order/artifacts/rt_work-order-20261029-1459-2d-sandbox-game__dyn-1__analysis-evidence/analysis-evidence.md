---
schema_version: 1
document_kind: node-artifact
content_language: "en"
audience: "internal"
work_order_id: "20261029-1459-2d-sandbox-game"
node_id: "rt_work-order-20261029-1459-2d-sandbox-game__dyn-1__analysis-evidence"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\runtime\\orchestration.xml"
---

# Analysis evidence — seed state, constraints and design options

## Scope

Evidence gathering for the create-mode work order. Product code is read-only in this node. The goal
document, the project bridge, the L1 convention record and the verbatim request are the inputs.

## Evidence and current state

### Confirmed facts from the seed

- `project/index.html` is a 960x540 page shell: `#game` canvas, `#hud`, `#hotbar` with four
  `span.slot` elements, and `#status`, loading five classic scripts in order.
- `js/config.js` exposes `tileSize=24`, `viewWidth=960`, `viewHeight=540`, `worldWidth=128`,
  `worldHeight=64`, `gravity=0.55`, `moveSpeed=3.2`, `jumpSpeed=8`, `reach=5`, six block ids
  (`air, grass, dirt, stone, wood, leaves`), `saveKey`, and `blockNames`.
- `js/world.js` has bounded `getBlock`/`setBlock`, solidity, flat generation at
  `ground = floor(height * 0.65)`, and JSON world serialization.
- `js/player.js` has placeholder gravity/movement only; there is no collision, jump or interaction.
- `js/render.js` draws a flat sky, flat-coloured tiles and a rectangle player; there is no camera
  follow, no texture, no highlight and no parallax.
- `js/main.js` boots a static first frame, sets `#status` to `ready`, and exposes `window.__sandbox`.
- `tests/world.test.js` contains six seed tests; `tools/page_check.py` performs static offline checks
  plus a headless Chrome marker/canvas check.

### Seed-test invariants that must not be weakened

The existing file `tests/world.test.js` asserts, for `createWorld(config.seed)`:

1. `getBlock(world, 0, 0) === air`.
2. `getBlock(world, 10, floor(height * 0.65)) === grass` — the surface at column 10 is exactly the
   base ground row.
3. `getBlock(world, 10, floor(height * 0.65) + 1) === dirt`.
4. `getBlock(world, 10, height - 1) === stone` — the bottom row is always stone.
5. `getBlock(world, -1, 0) === null`, out-of-range `setBlock` returns `false`.
6. Serialization round-trips block id at (12, 12) and the seed.
7. `isSolid(world, 0, 0) === false` and `isSolid(world, 0, height - 1) === true`.
8. `config.gravity > 0`, `config.blocks.air === 0`, `config.tileSize > 0`, `worldWidth/Height > 0`.

Invariant 2 is the sharp one: a naive noise height-map would break it. The generator must therefore
produce a zero surface offset at column 10. A wave built from `(x - 10)` terms satisfies that exactly
for every seed while still producing varied hills elsewhere; amplitude and frequency can vary by seed
without moving the zero crossing at x = 10. The bottom two rows stay stone, and the surface column
keeps at least three dirt rows, so invariants 2–4 hold together.

### Constraints from the bridge and request

- Offline, `file://`-runnable, no build step, no external library/CDN/font/network request.
- Browser modules must remain `require()`-able in Node without a DOM.
- `#status` contract: `booting` → `ready` after a successful first frame, red on runtime error; the
  page check samples the marker pixel at (15, viewport-15) and expects `rgb(46, 204, 113)` ± 70.
- `python tools/page_check.py` samples 12+ distinct colour buckets over the top-left 960x540 region.
- Do not delete or weaken seed tests; add coverage instead.
- English code comments and README; UTF-8 with LF; two-space JS indentation; existing UMD module style.
- No project Git commit.
- Temporary files under `work-orders/<id>/tmp/`.

### Confirmed facts from the environment

- Python 3.12.10, Node 24.13.1, `xcoding` CLI available. Chrome is discoverable by `page_check.py`.
- The `.xcoding` link inside `project/` resolves to the workshop directory, so the bridge and the
  work order live outside the page root; the page root has no `.xcoding` convention files of its own
  beyond the bridge.

## Reconciliation

No feature baselines exist (`feature_ids=[]`), so there is nothing to reconcile. The goal document and
the seed tests agree: feature work is additive; seed behaviour that the tests assert is preserved, and
new behaviour is proven by new tests. No conflict was found between the bridge, the request and the
seed contracts.

## Impact and risks

- **Rendering budget.** Full-window canvas with device-pixel-ratio scaling costs more than the seed's
  fixed 960x540. Mitigation: cap DPR at 2, draw only visible tiles, cache block texture patterns in
  offscreen canvases, and keep particle count bounded.
- **Collision correctness.** Axis-separated AABB resolution can tunnel at high speed or stick on
  corners. Mitigation: fixed-step accumulator (60 Hz), resolve X then Y, per-tile overlap checks, and
  unit tests for floor/wall/ceiling cases.
- **Terrain/test conflict.** Covered by the `(x - 10)` wave construction above; a test will assert the
  invariant for the default seed and for a second seed.
- **localStorage under `file://`.** Some browser configurations restrict storage for file origins.
  Mitigation: wrap every access in `try/catch`, fall back to an in-memory store, surface a non-blocking
  toast/indicator, and keep serialization independently unit-tested.
- **First-frame contract.** A heavy boot could delay `ready`. Mitigation: set `ready` after the first
  rendered frame and keep world generation O(width × height) with no blocking network.
- **Interaction ambiguity.** "empty adjacent cell" could mean cursor-under-pointer or face-adjacent.
  Mitigation: accept the empty cell under the pointer; when the pointer is over a solid block, choose a
  neighbouring empty cell adjacent to that block, requiring adjacency to a solid block and a
  player-AABB exclusion. This satisfies both readings and is testable.
- **Visual comparison bar.** A flat-colour rectangle world will lose the side-by-side comparison.
  Mitigation: layered sky, parallax hills, clouds, procedural tile textures, ambient occlusion, a
  character with animation, hover/selection feedback, particles, sound, a polished HUD and a pause
  overlay.

## Design options

### Option A — Minimal completion of each bullet

Flat or gentle terrain, rectangle blocks, rectangle player, four-slot hotbar, no sound or particles.
Fits the letter of the request but fails the stated quality contract: it would be visually similar to
the seed and lose to a strong one-shot attempt.

### Option B — Complete feature set with a distinctive presentation (recommended)

Keep the module split and seed-test invariants, then add:

- Seeded heightfield with hills, trees, caves, ore speckles and grass/flower decoration.
- Textured blocks drawn procedurally from a per-block palette and deterministic tile noise; ambient
  occlusion at exposed edges.
- A full-window, DPR-aware canvas; layered sky, sun glow, drifting clouds, parallax ridges, subtle
  vignette; smooth clamped camera with a slight look-ahead.
- A small explorer character with helmet, scarf, backpack, animated limbs, facing and landing squash.
- Mining with a pulsing reach outline, break particles and synthesized WebAudio feedback; placing with
  a ghost preview and a placement-flash; placement blocked inside the player.
- Eight-block hotbar (grass, dirt, stone, wood, leaves, sand, planks, glass) with number keys 1–8,
  wheel cycling, a large selected tile, swatch, name and keyboard hints.
- HUD with seed chip, save indicator, FPS-free clean typography, toast messages, and a help/pause
  overlay (`H`, `P`/`Escape`) with an in-page control legend.
- Persistence of seed, edited blocks, player position, hotbar selection and a timestamp; coalesced
  autosave plus save-on-pagehide; a "reset world with new seed" action.

### Option C — Larger meta-game (mobs, crafting, quests)

Out of scope: it risks the core loop, the offline/file-size budget and the verification window. Not
recommended for this work order.

## Recommendation

Option B. It preserves every seed contract, satisfies every functional bullet, and directly targets the
stated comparison bar with world variety, interaction feedback and a distinctive interface. Option B
is decomposed in the solution document into implementation units that can be verified independently.
