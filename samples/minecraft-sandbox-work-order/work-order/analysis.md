---
schema_version: 1
document_kind: work-order-analysis
content_language: en
work_order_id: "20261030-0000-minecraft-sandbox"
feature_ids: []
orchestration:
  main_tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261030-0000-minecraft-sandbox\\runtime\\orchestration.xml"
---

# Analysis — 2D Minecraft-style sandbox

## Evidence and current state

The seed project is a static shell: a 960x540 canvas, a HUD, a four-slot text hotbar, the `#status`
marker, and five classic UMD-style scripts (`config`, `world`, `player`, `render`, `main`) that boot a
flat world and mark it ready. Six Node tests cover the seed's world contract; `tools/page_check.py`
performs static asset/network checks and a headless-Chrome screenshot, status-pixel and canvas-colour
check. Movement, collision, mining, building, camera input, persistence, day/night, audio and every
prior capability are absent; the work order owns them. Environment: Python 3.12.10, Node v24.13.1,
Chrome available. `project/` is not a Git worktree, so no project commit exists or is expected. The
detailed evidence is in `artifacts/analysis-evidence/evidence.md`.

This is a `create` task, so the analysis records constraints and the quality contract rather than a
minimality presumption: the goal explicitly says matching the requirement list is the floor, and the
delivered experience must be at least as polished and feature-rich as a strong one-shot attempt, with
a reference-informed signature challenge.

## Capability map

Priorities follow `xc-work` `references/create-scope.md`: `must` is required for the request or
quality contract; `should` materially improves the experience; `non-goal` is deliberate and sourced.
The map is a fidelity instrument, not a breadth target.

| # | Capability | Source | Priority | User value | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | Seed-driven procedural terrain with grass, dirt and stone, plus surface height variety and vegetation | Request | must | The world itself; seeds make worlds repeatable and shareable | Same seed rebuilds the identical world; another seed differs visibly; grass/dirt/stone present; trees on the surface | `tests/generation.test.js`; screenshot |
| M2 | Player gravity, left/right movement, jumping and solid collision | Request | must | Embodied play in the world | Falls and lands, cannot pass through solids on any side, jumps only from the ground, stays inside world bounds | `tests/player.test.js`; browser check |
| M3 | Left-click mining of a block within reach, with feedback | Request | must | The core verb | Reachable solid removed and added to stock; out-of-reach refused; crack stages and particles | `tests/interaction.test.js`; screenshot |
| M4 | Right-click placement into an empty adjacent cell, never inside the player | Request | must | The second core verb | Placement validates empty target, adjacency, reach, player overlap and stock | `tests/interaction.test.js` |
| M5 | Hotbar with at least four block types, number-key selection and clearly visible selected state | Request | must | Choosing building material | Nine slots; keys 1-9 select; selected slot visibly and accessibly marked | `tests/ui.test.js`; screenshot |
| M6 | Camera follows the player and stays inside world bounds | Request | must | You can see where you move | Camera centres when possible, clamps at all edges, smooth follow | `tests/camera.test.js` |
| M7 | World and player state saved to `localStorage` and restored | Request | must | Sessions continue | Round-trips world edits, player, inventory, selection, time and settings; corrupt data ignored | `tests/storage.test.js` |
| M8 | Offline delivery: `file://`, no network, no external assets, `#status` marker contract | Request + project | must | Double-click and it runs | Static checks clean; boots ready; canvas non-blank | `tools/page_check.py` |
| M9 | Clean readable code and a controls note | Request + project | must | The result is understandable and usable | README documents controls, checks and architecture; code organised in small modules | README and review |
| M10 | Automated suite at or above 52 tests including the six seed tests | Prior + project | must | Behaviour stays protected | Suite passes with >= 52 tests; seed test file untouched | `node --test` |
| M11 | Nine-slot hotbar with per-block inventory counts | Prior | must | Stock is visible while building | Every slot shows a count that changes on mine/place; empty stock blocks placement | `tests/interaction.test.js`; screenshot |
| M12 | Numeric seed entry | Prior | must | Replay and share worlds | Valid integer seeds rebuild the world; invalid input is rejected with feedback | `tests/ui.test.js`; browser check |
| M13 | Day/night cycle | Prior | must | Atmosphere and time | Clock advances; sky, light, sun/moon change; time persists | `tests/daynight.test.js`; screenshots |
| M14 | Pause | Prior | must | Stop without losing state | Simulation and time freeze; overlay shows; resume continues | `tests/ui.test.js`; screenshot |
| M15 | Procedural audio with mute | Prior | must | Physical feedback and control | Distinct sounds; mute persists and silences output | `tests/audio.test.js` |
| M16 | Reduced-motion support | Prior | must | Accessibility | CSS media query and reduced JS motion when the preference is set | `tests/ui.test.js`; forced-reduced-motion render |
| M17 | Wheel selection | Prior | must | Fast palette switching | Wheel cycles slots with wrap-around | `tests/interaction.test.js` |
| M18 | 1280-wide scaling | Prior | must | Uses wide screens | `min-width: 1280px` scaling keeps proportions | CSS assertion; 1280 screenshot |
| M19 | Coordinate readout | Prior | must | Orientation | Live block coordinates and depth displayed | `tests/ui.test.js`; screenshot |
| M20 | Eighth hotbar block | Prior | must | Palette breadth | Slot 8 holds a distinct placeable block present in the model | `tests/interaction.test.js` |
| S1 | Visible mining/placement feedback: hover outline, crack stages, particles | Reference + quality bar | should | Actions feel physical and legible | Crack overlay while mining; particle burst on break/place; valid/invalid hover state | Render-helper tests; screenshot; visual review |
| S2 | Distinct procedural sound design | Reference + prior quality | should | Feedback beyond the visual | Mine/place/jump/select sounds differ; mute toggles | `tests/audio.test.js` |
| S3 | Visual depth and variety: parallax hills and clouds, textured tiles, depth shading, trees, caves | Reference + quality bar | should | The world reads as a place, not a grid | Screenshots show layered background, depth shading and vegetation | Screenshots; visual review |
| S4 | Polished HUD and onboarding: help panel, toasts, pause overlay, hover block info | Reference + quality bar | should | First-time players can start immediately | Help and pause overlays list controls; toasts confirm save/seed changes | Screenshots; visual review |
| S5 | In-page controls note | Request + quality bar | should | Controls discoverable in-page | Help panel lists all controls | Screenshot; `tests/ui.test.js` |

Reference-observed capabilities the request does not ask for — mobs/combat, health/hunger/survival
inventory, crafting, multi-biome worlds — are recorded as open decisions (below). They are not
classified as non-goals by inference and they do not remove any requested capability.

### Signature-experience table

| Reference | Signature capability | Evidence | Goal coverage | Decision |
| --- | --- | --- | --- | --- |
| Minecraft (named in the request) | Break/place feedback: selection outline, staged breaking, particles, sound | Block breaking and placing in Minecraft are staged and audible | Mechanics requested; feedback absent | **must** — sharpens M3/M4 into S1/S2 |
| Minecraft | Day/night change of light and sky | A defining ambient system of the reference | Absent from the request, present in the prior inventory | **must** M13; recorded as continuity, not a new demand |
| Minecraft | Seed-driven, layered terrain | Seeded world generation is a headline feature | Literal coverage in M1 | **should** S3 — depth and trees make "procedural" legible |
| Terraria (2D exemplar) | Parallax background and tile variety | Terraria's layered backgrounds sell 2D depth | Absent | **should** S3 — layered sky/hills and textured tiles |
| Terraria | Side-on mining/building with a palette | The genre's core loop in 2D | Covered by M3/M4/M5 | **must** as requested; no extra feature import |

The signature set is reduced to five decision-changing rows because the deliverable is one bounded
page: each row changes either the accepted matrix or the quality contract, and no row is padding.

## Prior capability dispositions

Source: cumulative prior standard versions (the binding run prompt supplies the inventory; the
inventory has no per-item version tags, so item-level provenance is the inventory itself).

| # | Prior capability | Disposition | Reason / impact | Source |
| --- | --- | --- | --- | --- |
| P1 | Per-block inventory counts | improve | Counts on every slot; mine adds, place spends, empty stock refuses placement | Prior inventory; M11 |
| P2 | 52 automated tests including seed tests | preserve | Floor kept; seed file untouched; new suites add coverage | Prior inventory; bridge |
| P3 | Reduced-motion support | improve | CSS query plus JS particle/bob reduction | Prior inventory |
| P4 | Wheel selection | preserve | Wheel cycles nine slots and wraps | Prior inventory |
| P5 | 1280-wide scaling | preserve | `min-width: 1280px` scaling media query | Prior inventory |
| P6 | Audio/mute | improve | Procedural WebAudio SFX, persisted mute, `M` shortcut | Prior inventory |
| P7 | Numeric seed entry | improve | Validated seed field rebuilds world and updates state | Prior inventory |
| P8 | Pause | improve | `P`/`Escape` freeze simulation and time; overlay; state persists | Prior inventory |
| P9 | Eighth hotbar block | preserve | Nine distinct blocks; slot 8 cobblestone, slot 9 glass | Prior inventory |
| P10 | Day/night | improve | Continuous clock drives sky, light, sun/moon, stars, HUD label | Prior inventory |
| P11 | Nine-slot hotbar | preserve | Nine slots with digits, icons, selection and counts | Prior inventory |
| P12 | Coordinates | improve | Live block X/Y and depth in the HUD | Prior inventory |

No item is replaced, retired or deferred, so no replace/retire source is required and no item is
dropped. This table is the canonical record the solution matrix and verification must map to.

## Goal-versus-request comparison

Every requested outcome is present in the goal's scope (M1-M9). The goal's only added constraint is
the delivery-form resolution — local sibling files rather than one literal file — which the request
itself permits ("or local files next to it") and the project bridge requires for Node-loadable
modules; it is recorded as `user`-sourced, not an exclusion. The goal adds the prior capability set,
the quality contract and the screenshot/visual-review requirement from the binding prompt, each with
a `user` or `project` source. No material capability is missing, no material exclusion exists, and no
`goal-authored` binding exclusion exists, so no exclusion needs user confirmation. No capability is
ambiguous enough to require a user decision; the choices the request leaves open (palette, world
size, art direction) are implementation choices recorded below as open decisions.

## Impact and risks

- **Seed-test compatibility.** The generation must keep column 10 grass at `floor(height*0.65)`, dirt
  below and stone at the bottom. Mitigation: flat spawn plateau near the origin; the untouched seed
  suite proves it.
- **Playability of any seed.** Deterministic spawn search plus a guaranteed flat area near spawn.
- **Persistence robustness.** Schema-checked payload, defensive parsing, safe fallback to a fresh
  world and a visible message; settings stored separately.
- **Audio autoplay policy.** Audio context created/resumed on first gesture; silent until then.
- **Performance.** Pre-rendered tile variants, visible-cell culling, capped particles, clamped delta.
- **Scope drift into survival systems.** The accepted matrix is the boundary; extras stay open
  decisions rather than silently inferred exclusions.
- **Visual quality risk.** Mitigated by screenshot inspection at 960, 1280 and forced reduced motion,
  plus an independent visual review with required findings fixed before closure.

## Alternatives and recommended direction

1. **Terrain.** Chosen: deterministic sine-mix height field with a flat spawn plateau, layered
   grass/dirt/stone/sand, caves and seeded trees. Rejected: keeping the flat generator (fails the
   request), full value noise (more code, no visible benefit at this scale).
2. **Rendering.** Chosen: canvas with pre-rendered textured tile variants, parallax sky/hills/clouds,
   depth shading, sprite animation and particles. Rejected: flat rect fills (poor quality), DOM tiles
   (heavy).
3. **Physics.** Chosen: axis-separated AABB collision with fixed sub-steps; testable without a DOM.
4. **Persistence.** Chosen: one versioned JSON payload under the existing save key plus a settings
   key, defensively validated. Rejected: many individual keys (non-atomic, harder to validate).
5. **Audio.** Chosen: procedural WebAudio tones/noise on gesture, persisted mute.
6. **UI.** Chosen: static accessible DOM overlay (HUD, hotbar, seed panel, help/pause overlays,
   toasts) over one canvas.
7. **Day/night.** Chosen: continuous normalised clock with palette interpolation and phase labels.
8. **Accessibility and scaling.** Chosen: CSS media queries plus JS `matchMedia` checks for
   reduced motion, and a 1280-wide scaling query.

Recommended direction: implement all M1-M20 and S1-S5 in the modular static-page architecture above,
keep the seed modules' UMD style and testability, and verify with the project's two commands plus
screenshot review at the three required viewports/settings.

## Open decisions (no user available)

| Open decision | Why it is open | Recorded handling |
| --- | --- | --- |
| Mobs, combat, health/hunger, crafting and survival inventory are not requested but exist in the reference | The request is silent and no user is available to accept them as a should or non-goal | Not bound and not delivered this version; recorded here so a later request can add them. This is not a silent exclusion of anything requested. |
| Multi-biome world generation | Reference-observed, request silent, and not needed for the requested seeded terrain | Deferred by the same open decision; the generator still varies height, caves and vegetation per seed |
| Exact block palette beyond the required four | The request names a minimum, not a full list | Implementation choice recorded in the solution: nine placeable blocks, slot 8 cobblestone and slot 9 glass |
| World size, art direction and UI styling | Request leaves them open | Implementation choices recorded in the solution and proven by screenshots |

No open decision blocks an accepted must capability: each is either a reference extra or an
implementation detail, and every requested capability has an accepted path.
