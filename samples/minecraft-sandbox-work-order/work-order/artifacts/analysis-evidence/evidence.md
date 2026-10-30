---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-0000-minecraft-sandbox"
node_id: "rt_work-order-20261030-0000-minecraft-sandbox__dyn-1__analysis-evidence"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261030-0000-minecraft-sandbox\\runtime\\orchestration.xml"
---

# Create analysis evidence — 2D Minecraft-style sandbox

## Scope

Evidence and reasoning for the create work order, feeding `analysis.md`. Inputs: the binding run
prompt, `goal.md`, the project bridge `.xcoding/WORKFLOW.md`, and the seed project under
`project/`. No implementation, baseline or sample outside the isolated workspace was consulted.

## Confirmed facts

### Seed state (evidence: direct file inspection)

| File | Current state |
| --- | --- |
| `project/index.html` | Page shell: `<canvas id="game">` 960x540, `#hud`, `#hotbar` with four static text slots, `#status` marker, five classic `<script>` tags. |
| `project/js/config.js` | Frozen constants: tile 24, view 960x540, world 128x64, gravity 0.55, move speed 3.2, jump speed 8, reach 5, save key `xc-sandbox-sample-v1`, block ids air/grass/dirt/stone/wood/leaves. There is no `seed` constant. |
| `project/js/world.js` | Flat ground at `floor(height*0.65)` with grass/dirt/stone bands; bounded `getBlock`/`setBlock`; JSON serialization round-trip; `isSolid`. |
| `project/js/player.js` | `createPlayer` and a skeleton `stepPlayer` that applies gravity and horizontal intent but performs no collision, no jumping and no world interaction. |
| `project/js/render.js` | Flat sky gradient and block rectangles; static camera object; blocky player placeholder. |
| `project/js/main.js` | Boots a flat world, renders one frame, marks `#status` ready, starts a requestAnimationFrame loop; no input, no camera update, no save. |
| `project/tests/world.test.js` | Six passing tests covering config contract, dimensions/seed, ground line, bounded access, serialization round-trip and solidity. |
| `project/tools/page_check.py` | Static checks (required ids `game`, `status`, `hud`, `hotbar`; local assets; no network references) plus headless Chrome screenshot, status-marker pixel and canvas colour buckets. Accepts `--screenshot`. |
| `project/css/style.css` | Dark panel UI, 960-wide app, four-slot hotbar, status-marker colours. |
| `project/README.md` | Seed documentation with target controls and constraint list. |

The seed is deliberately incomplete: movement, collision, mining, building, camera input,
persistence, day/night, audio and every prior capability are absent. The work order owns all of them.

### Environment (confirmed by command)

`python --version` -> 3.12.10; `node --version` -> v24.13.1; `python tools/page_check.py` is the
declared browser check and locates Chrome/Edge on the host. `project/` is not a Git worktree, so the
work order records that no project commit is possible or desired.

### Project constraints (evidence: `.xcoding/WORKFLOW.md`)

- English throughout; UTF-8 with LF; two-space JavaScript indentation; existing UMD-style modules.
- No build step; page must work from `file://`.
- Verification commands: `node --test "tests/**/*.test.js"` and `python tools/page_check.py`.
- `#status` marker contract (`booting`, `ready`, `error`); modules loadable in Node.
- Never delete or weaken the seed tests; add coverage.
- No third-party libraries, CDNs, external fonts or network requests.
- Change report is waived (`work_order.requires_report=false`, `user_waived`); no project Git commit.

### Prior accepted capability inventory (evidence: binding run prompt, cumulative prior versions)

Twelve items: per-block inventory counts; 52 automated tests including the seed tests;
reduced-motion support; wheel selection; 1280-wide scaling; audio/mute; numeric seed entry; pause;
the eighth hotbar block; day/night; nine-slot hotbar; coordinates. Title/version provenance is not
recorded in the supplied inventory, so the inventory is cited as "cumulative prior standard
versions 0.3.4-0.3.5" per the run context and treated as accepted prior intent. No item is
retired or replaced.

### Domain reference (evidence available)

- **Minecraft (Java Edition)** — named directly by the request. Its legible signature features are
  block-grid interaction with break/place feedback, a hotbar with selection, seeded worlds,
  day/night, and layered terrain.
- **Terraria** — the recognised 2D sandbox exemplar. Its legible signature features are side-on
  mining/building, parallax backgrounds, and rich tile variety.

The evidence is domain knowledge about widely documented public products; the work order makes no
network request and does not copy assets or code. The signature set is deliberately small and
decision-changing; it is not a feature-count target.

## Capability map

| # | Capability | Source | Priority | User value | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | Seed-driven procedural terrain with grass, dirt and stone | Request | must | The world is the game; a seed makes worlds shareable | Same seed rebuilds identical world; different seed differs; three base materials present | `tests/generation.test.js`; screenshot |
| M2 | Player gravity, run, jump, collision | Request | must | Basic embodied play | Falls to ground, stops at walls, jumps only from ground, cannot tunnel | `tests/player.test.js`; browser check |
| M3 | Left-click mining within reach | Request | must | The core verb of the genre | Reachable solid removed, inventory +1; unreachable refused | `tests/interaction.test.js` |
| M4 | Right-click placement in empty adjacent cell, never inside the player | Request | must | Building is the second core verb | Placement validates empty cell, adjacency, reach, player overlap, stock | `tests/interaction.test.js` |
| M5 | Hotbar with at least four block types, number keys, visible selection | Request | must | Choosing what to build with | 9 slots, keys 1-9 select, selected class/aria state | `tests/ui.test.js`, `tests/interaction.test.js`; screenshot |
| M6 | Camera follows player and stays in bounds | Request | must | You can see where you are going | Camera centres on player when possible, clamps at world edges | `tests/camera.test.js` |
| M7 | World and player state saved to localStorage and restored | Request | must | Continuity across sessions | Round-trip world edits, player, hotbar, time, settings; corrupt payload ignored | `tests/storage.test.js` |
| M8 | Offline single-page delivery, file://, no network, status marker | Request + project | must | The page opens by double-click | Static scan clean; boot to ready; canvas non-blank | `tools/page_check.py` |
| M9 | Clean readable code and controls note | Request + project | must | The result can be understood and used | README documents controls, checks, architecture; modules readable | README inspection; review |
| M10 | Automated test suite at or above 52 including the six seed tests | Prior + project | must | Behaviour is protected and reviewable | Suite passes with >= 52 tests, seed file unchanged | `node --test` |
| M11 | Nine-slot hotbar with per-block counts | Prior | must | Stock is visible while building | 9 slots each with count; counts change on mine/place | `tests/interaction.test.js`, `tests/ui.test.js`; screenshot |
| M12 | Numeric seed entry | Prior | must | Worlds can be replayed and shared | Valid integer seeds rebuild the world; invalid input is refused with feedback | `tests/ui.test.js`, `tests/world.test.js`; browser check |
| M13 | Day/night cycle | Prior | must | Time and atmosphere make the world feel alive | Time advances, sky/light changes, time persists | `tests/daynight.test.js`; screenshots |
| M14 | Pause | Prior | must | The player can stop without losing state | Physics and time freeze; overlay visible; resume restores | `tests/ui.test.js`; screenshot |
| M15 | Procedural audio with mute | Prior | must | Mining/placing feel physical; mute respects preference | Distinct SFX, mute persisted, no audio node when muted | `tests/audio.test.js` |
| M16 | Reduced-motion support | Prior | must | Accessible for motion-sensitive players | CSS media query plus reduced particle/bob behaviour when requested | `tests/ui.test.js`, CSS assertion; forced-reduced-motion render |
| M17 | Wheel selection | Prior | must | Fast palette switching | Wheel cycles slots with wrap-around | `tests/interaction.test.js` |
| M18 | 1280-wide scaling | Prior | must | The page uses wide screens | Media query at 1280 scales the app and keeps proportions | CSS assertion; 1280 screenshot |
| M19 | Coordinate readout | Prior | must | Orientation and shareability | Live block coordinates and depth in the HUD | `tests/ui.test.js`; screenshot |
| M20 | Eighth hotbar block | Prior | must | Palette breadth beyond the minimum | Slot 8 is a distinct placeable block and is present in the model | `tests/interaction.test.js`, `tests/ui.test.js` |
| S1 | Visible mining/placement feedback (crack stages, particles, hover outline) | Reference + request quality bar | should | Actions feel connected and legible | Crack overlay while mining; particles on break/place; valid/invalid hover states | Screenshot, review, pure render helper tests |
| S2 | Distinct procedural sound design with mute control | Reference + prior quality | should | Feedback beyond the visual | Jump/mine/place/select sounds differ; mute toggles | `tests/audio.test.js`; browser check |
| S3 | Visual depth and variety (parallax hills, clouds, textured tiles, depth shading, trees, caves) | Reference + quality bar | should | The world reads as a place, not a grid | Screenshot inspection shows layered background, depth and vegetation | Screenshots; review |
| S4 | Polished HUD and onboarding (help panel, toasts, pause overlay, hover info, keyboard hints) | Reference + quality bar | should | First-time players can start immediately | Help/pause overlays list controls; toasts confirm save/seed changes | Screenshots; review |
| S5 | In-page controls note | Request + quality bar | should | Controls discoverable without README | Help panel lists every control | Screenshot; `tests/ui.test.js` |

Reference-observed capabilities the request is silent about — mobs/combat, health/hunger/survival
inventory, crafting, multi-biome generation — are **not** classified as non-goals by inference. No
user is available to confirm them, so they are recorded as open decisions in `analysis.md` and are
not part of the accepted matrix for this version.

### Signature-experience table

| Reference | Signature capability | Evidence | Current goal coverage | Decision (with user value) |
| --- | --- | --- | --- | --- |
| Minecraft (named in request) | Break/place feedback: selection outline, crack stages, particles, sound | Block-breaking in Minecraft is visibly staged and audible | Partial — mechanics requested, feedback absent | **must** S1/S2 sharpened onto M3/M4: the core verbs must feel physical |
| Minecraft | Day/night cycle changing light | Minecraft's sun/moon cycle is a defining ambient system | Absent in request, present in prior inventory | **must** M13 (prior, not a new demand) |
| Minecraft | Seeded world + layered terrain | Seed-driven world generation is a headline feature | Covered literally (seed + grass/dirt/stone) | **should** S3 depth: layered caves/trees make "procedural" legible; must only insofar as M1 |
| Terraria (2D exemplar) | Parallax background and tile variety | Terraria's layered backgrounds sell 2D depth | Absent | **should** S3: layered sky/hills textures make the 2D world read as a place |
| Terraria | Side-on mining/building at scale with palette | 2D sandbox interactions are the genre's core | Covered by M3/M4/M5 | **must** as already requested; no new feature import |

The set is reduced to five decision-changing rows because the task is a single bounded page; each
row changes either the quality contract or the accepted matrix.

## Goal-versus-request comparison

| Requested outcome | Goal coverage | Flag |
| --- | --- | --- |
| Procedural terrain from a numeric seed, grass/dirt/stone | Covered (M1, M12) | none |
| Gravity, left/right, jumping, collision | Covered (M2) | none |
| Left-click mine within reach; right-click place adjacent; never inside player | Covered (M3, M4) | none |
| Hotbar >= 4 types, number keys, visible selection | Covered (M5) and extended by prior M11/M20 | none |
| Camera follows and stays in bounds | Covered (M6) | none |
| localStorage save/restore | Covered (M7) | none |
| Clean code and controls note | Covered (M9, S5) | none |
| Single page or local files, no build/network/libraries | Covered (M8) | Delivery-form question resolved from the request's own "local files next to it"; recorded, not excluded |
| Quality bar from the run prompt | Covered in the goal's quality contract (comparison target, screenshot iteration, independent review, signature challenge) | none |
| Prior capability inventory | Enumerated in the goal; canonical dispositions below | none |

No material capability is missing from the goal, and the goal adds no unsourced exclusion. No
`goal-authored` binding exclusion exists in the goal. Therefore no user decision is needed to make
any exclusion binding.

## Prior capability dispositions (canonical)

| # | Prior capability | Disposition | Reason / impact | Source |
| --- | --- | --- | --- | --- |
| P1 | Per-block inventory counts | improve | Counts become visible on every hotbar slot and change on mine/place; adds stock-awareness feedback. Impact: no prior behaviour lost; placement now also respects stock. | Prior inventory; request's hotbar requirement provides the surface |
| P2 | 52 automated tests including seed tests | preserve | Floor kept at 52; seed file untouched; new suites cover generation, physics, interaction, storage, UI, audio, day/night. Impact: regression protection grows. | Prior inventory; project bridge "do not weaken seed tests" |
| P3 | Reduced-motion support | improve | CSS media query retained and extended so JS reduces particles and disables bob when the preference is set. Impact: better accessibility, no visual loss for default users. | Prior inventory |
| P4 | Wheel selection | preserve | Wheel over the game cycles the nine slots with wrap-around. | Prior inventory |
| P5 | 1280-wide scaling | preserve | A `min-width: 1280px` media query scales the 960-wide app while keeping proportions. | Prior inventory |
| P6 | Audio/mute | improve | Procedural WebAudio SFX for mine/place/jump/select with a persisted mute toggle and `M` shortcut. Impact: richer feedback; still silent when muted or after restore. | Prior inventory |
| P7 | Numeric seed entry | improve | A seed field with validation and an apply button rebuilds the world and updates the HUD/state; invalid input is rejected with a message. | Prior inventory |
| P8 | Pause | improve | `P`/`Escape` toggles pause; simulation and day/night freeze; overlay explains the state; time persists. | Prior inventory |
| P9 | Eighth hotbar block | preserve | Nine slots hold nine distinct placeable blocks; slot 8 is cobblestone and slot 9 glass. | Prior inventory |
| P10 | Day/night | improve | Continuous cycle drives sky gradient, sun/moon, stars, ambient tint and a HUD time label; time persists. | Prior inventory |
| P11 | Nine-slot hotbar | preserve | Nine slots with digits, icons, selected state and counts. | Prior inventory |
| P12 | Coordinates | improve | Live block X/Y plus surface depth shown in the HUD. | Prior inventory |

No prior item is replaced, retired or deferred, so no replace/retire source is needed. No item is
omitted; an undispositioned item would block solution approval.

## Design options considered

1. **Terrain generation.** (a) Keep the flat seed generator — fails the "procedural terrain from a
   numeric seed" reading and world variety. (b) Sine/noise height field with a flat spawn plateau and
   deterministic tree/cave decoration — chosen: readable, deterministic, no dependency, and
   compatible with the seed tests at column 10. (c) Full value-noise implementation — more code and
   tuning for no visible gain at this scale.
2. **Rendering.** (a) Direct `fillRect` per tile per frame — simple but flat, slow at texture detail.
   (b) Pre-rendered tile variants on an offscreen canvas plus parallax layers, depth shading,
   particles and sprite animation — chosen for visual quality and stable frame cost. (c) DOM tiles —
   rejected: thousands of nodes, poor animation.
3. **Physics.** Axis-separated AABB collision over block cells with fixed sub-steps — chosen; simple,
   testable without a DOM and robust at the configured speeds.
4. **Persistence.** One JSON payload under the existing save key with a schema version field,
   defensive parsing, settings under a sibling key — chosen over per-field keys: atomic and easy to
   validate. LocalStorage failures degrade to an in-memory session rather than breaking boot.
5. **Audio.** Procedural oscillators/noise through WebAudio created on first user gesture — chosen:
   no assets, offline, no autoplay violation. Mute is persisted in settings.
6. **UI.** Static DOM overlay (HUD, nine-slot hotbar, seed panel, help/pause overlays, toasts) over a
   single canvas — chosen over canvas-drawn UI for accessibility, focus handling and testability.
7. **Day/night.** A continuous normalised clock driving a small palette interpolation function with
   labelled phases — chosen over scripted keyframes: cheap, testable, smooth.
8. **Reduced motion and scaling.** CSS media queries plus JS `matchMedia` checks — chosen because both
   preferences are environment-driven and must work without reload.

## Risks and mitigations

- **Seed tests constrain generation.** Column 10 must keep grass at `floor(height*0.65)`, dirt below,
  stone at the bottom. Mitigation: flat spawn plateau masks hill amplitude near the origin; verified
  by the untouched seed tests.
- **Pathological seeds producing unplayable spawns.** Mitigation: deterministic spawn search for a
  surface with two air cells; generation keeps a minimum flat area near spawn.
- **localStorage unavailable or corrupt.** Mitigation: try/catch, schema validation, fallback to a
  fresh world and a recorded toast; no exception escapes boot.
- **Performance on dense screens.** Mitigation: pre-rendered tiles, only visible cells, capped
  particles, clamped delta time.
- **Autoplay audio restriction.** Mitigation: create/resume the audio context only on first pointer or
  key interaction; remain silent until then.
- **Scope creep into survival systems.** Mitigation: the accepted matrix above is the boundary;
  reference-observed survival systems stay open decisions, not silent exclusions.
- **Visual review late discovery.** Mitigation: render and screenshot after implementation and before
  the review node, then fix required findings with a repair node and re-verify.

## Conclusion

The goal is faithful to the request, adds no unsourced exclusion and carries the quality contract.
The capability map covers every requested capability, every prior inventory item has a preserve or
improve disposition, and the signature table adds only the feedback/depth polish the quality bar
needs. The recommended solution direction is a modular static page: seeded generator, AABB physics,
canvas renderer with layered art and particles, DOM HUD/hotbar, localStorage persistence, procedural
audio, day/night, pause, reduced motion, wheel selection, 1280-wide scaling, numeric seed entry and
coordinates, with a test suite at or above 52 tests.
