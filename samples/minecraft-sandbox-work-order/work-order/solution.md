---
schema_version: 1
document_kind: work-order-solution
content_language: en
work_order_id: "20261028-1731-implement-minecraft-sandbox"
feature_ids: []
orchestration:
  main_tree_ref: "C:/dev/xcoding-workflow-dev/minecraft-sandbox-workshop/.xcoding/work-orders/20261028-1731-implement-minecraft-sandbox/runtime/orchestration.xml"
---

# Solution: Offline 2D Sandbox

## Selected change

Implement the sandbox as one cohesive change inside the existing static, UMD-module layout. The page
keeps `index.html` at the project root and continues to work from `file://`; no framework, build step,
asset pipeline or network request is introduced. Two new pure modules are added for testability:
`js/interaction.js` (reach, mining, placement and player-overlap rules) and `js/save.js`
(storage-injected world/player persistence).

### Constants and world model

`js/config.js` gains an explicit numeric `seed` (`20261028`) and playable frame-based physics:
`gravity=0.03`, `moveSpeed=0.18`, `jumpSpeed=0.45`, terminal fall speed `0.9`, `reach=5`, spawn column
`12`, fixed update step 1/60 s. Block ids, world size (128x64), tile size (24), serializer shape and
`saveKey` remain compatible. `js/world.js` keeps the flat spawn plateau over columns `0..23` at the
original `floor(height * 0.65)` line, then blends into a smooth seeded multi-sine height map east of
the plateau; the surface is one grass row, three dirt rows and stone below. A deterministic
`mulberry32` stream (seeded from the world seed with a fixed mixing constant) places occasional trees
(wood trunk plus leaf canopy) with one guaranteed tree near the spawn plateau. A `surfaceHeightAt`
helper returns the pre-tree surface height for spawn and tests. `getBlock`/`setBlock` keep their
bounded contract, and serialization remains JSON over the block array.

### Player and collision

`js/player.js` replaces the skeleton step with a frame-based step:

- Horizontal intent sets `vx = ±moveSpeed` (both keys cancel); `vy += gravity` is clamped to the
  terminal fall speed; a jump sets `vy = -jumpSpeed` only while grounded.
- The player is an AABB: horizontal span `x ± width/2`, vertical span `y - height .. y`, with
  `width=0.7`, `height=1.8` tiles.
- Movement is applied in substeps of at most 0.25 tiles. Horizontal and vertical axes are resolved
  separately; on overlap the player snaps to the collided tile edge, the axis velocity is cleared, and
  downward contact sets `onGround`. Out-of-world sides and the bottom are solid; the sky is open.
- Grounding is re-probed after each step, so jumping, walking off a ledge and landing all behave
  consistently.

### Interaction

`js/interaction.js` provides DOM-free rules used by both tests and `main.js`:

- `cellFromScreen(camera, screenX, screenY, tileSize)` maps pointer pixels to tile coordinates.
- `canMine` accepts a non-air block whose centre is within `reach` of the player centre; `mineBlock`
  clears it.
- `canPlace` requires an in-bounds air cell, a non-air selected block, reach, at least one solid
  orthogonal neighbour (no floating blocks), and no overlap with the player AABB. `placeBlock`
  applies the rule. `adjacentPlacementCell` resolves a right-click on a solid block to the nearest
  valid empty orthogonal neighbour, so right-clicking a face places beside it; right-clicking an empty
  cell places there when it is adjacent to a solid block.

### Camera, rendering and page

`js/render.js` exports `cameraForPlayer(world, player)`, which centres on the player and clamps to
`[0, worldPixelSize - viewSize]` on both axes; `main.js` recomputes it every update. The renderer keeps
the sky gradient and adds per-tile texture accents, a more readable player figure, and a target
outline. `index.html` gains a persistent control hint and a selected-block readout inside `#hud`;
`css/style.css` styles the hint, block swatches and the `is-selected` state. The four existing
hotbar slots stay, now with `aria-pressed`, number-key selection (`1`-`4`), click selection and a
visible selected background/border.

### Boot, loop and persistence

`js/main.js` boots in this order: locate elements, attempt a guarded load through
`js/save.js` using `window.localStorage`, fall back to a freshly generated world and plateau spawn,
wire keyboard/pointer input, render the first frame, set `#status` ready, then run a fixed-step
`requestAnimationFrame` loop (accumulator capped at five steps). Mining and placement mutate the
world, mark it dirty and save immediately; the selected block, world and player position are also
saved on a throttled interval and on `beforeunload`. Errors set the red status state through the
existing window error handlers. The exposed `window.__sandbox` object remains for diagnostics.

`js/save.js` writes versioned JSON (`version:1`) containing the full block array, seed, dimensions,
player position/velocity and selected block, and validates every field on load. Corrupt, missing or
unreadable storage returns `null` rather than throwing.

### Tests and documentation

New test files (`tests/terrain.test.js`, `tests/player.test.js`, `tests/interaction.test.js`,
`tests/save.test.js`, `tests/render.test.js`) cover terrain determinism and layers, block bounds,
landing/wall/jump collision, reach and placement rules including player overlap, camera clamping,
and save/load round-tripping with an in-memory storage. `tests/world.test.js` is left unchanged.
`project/README.md` is updated to describe what was built, how to open it, the controls, the save
behavior, the architecture and both verification commands.

## Feature baseline impact

There are no associated features (`feature_ids=[]`), so no feature baseline is read, reconciled or
modified, and no `.xcoding/features/<feature-id>/` directory is created. The change is confined to
the sample consumer project. No project Git commit is created because the bridge and the user decision
assign the sample's single scoped commit to the enclosing repository. The change-report stage is
waived (`work_order.requires_report=false`, `work_order.report_skip_reason=user_waived`), so no report
group is mounted.

## Implementation and migration strategy

1. Extend `js/config.js` with the seed, tuned physics, spawn column and hotbar list, keeping every
   existing exported name.
2. Rewrite `js/world.js` generation with the seeded height map, plateau, layers and trees while
   preserving `createWorld`, `getBlock`, `setBlock`, `isSolid`, `serializeWorld` and
   `deserializeWorld`.
3. Rewrite `js/player.js` with AABB collision, substepping, jumping and ground detection.
4. Add `js/interaction.js` and `js/save.js` as UMD modules so Node and the browser share them.
5. Extend `js/render.js` with the camera helper, target outline and richer tile/player drawing.
6. Rewrite `js/main.js` boot, input, fixed-step loop, hotbar and persistence.
7. Update `index.html` and `css/style.css` with the hint readout and selected-state styling; preserve
   the required ids and the status marker contract.
8. Add the five focused test files without editing `tests/world.test.js`.
9. Rewrite `README.md` for the implemented game, controls, files and checks.

There is no data migration. Saved payloads are versioned and were never written by the seed, so a
missing or incompatible payload falls back to a new world. All authored text is UTF-8 with LF line
endings and two-space JavaScript indentation.

## Verification strategy

- `node --test "tests/**/*.test.js"`: the six seed tests plus the new terrain, player, interaction,
  save/load and camera tests. Terrain determinism is checked by generating the same seed twice and by
  comparing different seeds; collision is checked by stepping a player into a wall and onto ground;
  placement is checked against occupied cells, floating cells, out-of-reach cells and the player
  footprint; persistence is checked with an in-memory storage fake.
- `python tools/page_check.py --screenshot <workbench>/tmp/page-check.png`: static ids, local assets,
  no external network references, the green `#status` pixel and the non-blank canvas colour count.
  The screenshot is diagnostic evidence under `tmp/` and is never declared as an artifact.
- The full command output is captured in the verification node artifact so the evidence is retained
  under the workbench.
- Acceptance mapping: determinism/layers -> terrain tests; bounds -> world tests; collision ->
  player tests; placement -> interaction tests; save/load -> save tests; page contract -> page check;
  documentation -> README review; artifact placement -> runtime `artifacts` listing.

Residual risk: the headless harness proves rendering and boot, not human play feel; the retuned
physics is verified by logic tests and a rendered screenshot. `localStorage` availability on
`file://` is browser-dependent and is handled by falling back to a fresh world.
