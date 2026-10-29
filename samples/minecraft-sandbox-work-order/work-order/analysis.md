---
schema_version: 1
document_kind: work-order-analysis
content_language: "en"
work_order_id: "20261029-1459-2d-sandbox-game"
feature_ids: []
orchestration:
  main_tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\runtime\\orchestration.xml"
---

# Analysis — from seed shell to a playable, polished sandbox

## Evidence and current state

The seed is a working offline shell, not a game. It boots a 960x540 canvas, paints a flat
grass/dirt/stone world, draws a rectangle player and sets the `#status` marker to `ready`. Movement,
collision, jumping, mining, placing, camera follow, hotbar selection and persistence do not exist.
The module split (config → world → player → render → main, all UMD-style) is sound and should be kept
because the bridge requires Node-loadable modules and the seed tests require them.

The binding constraints are the project bridge and the seed tests. The bridge requires offline/
`file://` operation, no external assets, the `#status` contract, Node-loadable modules, the two
verification commands, English/UTF-8/LF text, two-space JavaScript and no project Git commit. The L1
convention record adds no other source and reports no conflict.

The sharpest engineering fact is a seed-test invariant: for `createWorld(config.seed)`,
`getBlock(world, 10, floor(worldHeight * 0.65))` must be grass, the row below must be dirt, and the
bottom row must be stone. A naive noise heightmap breaks that assertion. The analysis evidence node
records all eight invariants and the resolution: build the surface wave from `(x - 10)` terms so the
offset is exactly zero at column 10 for every seed, while amplitude and frequency still vary by seed.
The bottom two rows stay stone and the surface keeps at least three dirt rows.

The environment supplies Python 3.12, Node 24 and Chrome, so both project commands and headless
screenshot inspection are available without new tooling.

## Reconciliation

`feature_ids` is empty, so no feature baseline exists to reconcile. The goal, the bridge and the seed
tests are compatible: the goal adds behaviour and preservation requirements rather than changing seed
contracts. The only apparent tension — "procedural terrain with hills" versus the flat-surface seed
test — is resolved by the zero-crossing wave construction and will be covered by an added test for a
second seed as well.

## Impact and risks

The change touches every page file except the verification harness. The risk areas and mitigations are:

- **Rendering quality.** A flat-colour world loses the side-by-side comparison. The plan adds layered
  sky, parallax ridges, clouds, procedural tile textures, ambient occlusion, a character with
  animation, a pulsing reach outline and particles. DPR is capped and texture patterns are cached.
- **Collision correctness.** Axis-separated AABB resolution with a fixed 60 Hz accumulator avoids
  tunnelling and corner sticking; floor, wall, ceiling and head-bump cases get unit tests.
- **Persistence under `file://`.** Every `localStorage` access is guarded; a memory fallback and a
  visible save indicator keep the game playable if storage is restricted. Serialization is tested
  without a DOM.
- **Boot contract.** World generation is O(width × height) and synchronous; `#status` becomes `ready`
  only after the first successful frame, preserving the page-check contract.
- **Interaction semantics.** "Empty adjacent cell" is implemented as the empty cell under the pointer,
  or a neighbouring empty cell adjacent to the clicked solid block; placement requires solid adjacency,
  reach and a clear player AABB.
- **Scope creep.** Mobs, crafting and multiplayer are excluded. The feature set is fixed by the goal
  and the solution boundary.

## Alternatives

- **Option A — literal minimum.** Flat terrain, rectangles, four slots, no feedback. Cheap but fails
  the quality contract and would be visually dominated by the seed itself.
- **Option B — complete loop with a distinctive presentation (chosen).** Seeded hills, trees, caves and
  ore speckles; textured tiles; a full-window DPR-aware canvas; a character with animation; mining and
  placing feedback with particles and synthesized sound; an eight-block hotbar with number and wheel
  selection; seed/reset/save controls; a help and pause overlay; tested collision and persistence.
- **Option C — meta-game.** Mobs, crafting or quests. Excluded: it dilutes the core loop and threatens
  the offline, single-page and verification budget.

Option B meets every functional requirement, preserves every seed contract, and directly targets the
stated comparison bar. The solution document converts it into bounded implementation and verification
units.
