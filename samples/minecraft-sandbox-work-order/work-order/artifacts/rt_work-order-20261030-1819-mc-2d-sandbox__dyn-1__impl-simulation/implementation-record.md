---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-1819-mc-2d-sandbox"
node_id: "rt_work-order-20261030-1819-mc-2d-sandbox__dyn-1__impl-simulation"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Implementation record — simulation core (IU1)

## Scope

Implemented the accepted solution's simulation core under `project/js/` and its Node tests under
`project/tests/`. No presentation file (`index.html`, `css/style.css`, `render.js`, `ui.js`,
`audio.js`, `main.js`) was changed in this unit; page wiring is IU2's accepted scope.

## Evidence

### Changed paths

| Path | Bytes | Purpose |
| --- | --- | --- |
| `js/config.js` | 2979 | Nine-block catalogue in palette order (grass, dirt, stone, wood, leaves, sand, planks, glass, brick), colours, 32 px tiles, 128x64 world, physics, reach, time, save constants, starter kit with leaves at 0 |
| `js/rng.js` | 3228 | Deterministic hash, mulberry32, 1D/2D value noise and fbm helpers |
| `js/world.js` | 9026 | Exact flat spawn plateau (columns 0–24 at row 41), blend 25–26, seeded noise 27–127 clamped to rows 33–46, layers, dune sand patch, trees, caves above bedrock, bounded block access, legacy JSON and RLE serialization |
| `js/player.js` | 4871 | Axis-separated AABB tile collision with 0.2-tile sub-steps, gravity, jump, grounding, bounds clamp, delta clamp |
| `js/inventory.js` | 3065 | Per-block counts, add/consume with no negative state, serialization |
| `js/interaction.js` | 4562 | Mining and placement rules with structured `{ok, reason}` results: bounds, reach, occupancy, player AABB, support, empty palette slot |
| `js/persistence.js` | 4347 | Versioned payload with RLE blocks, memory storage adapter, empty/corrupt/version/unavailable outcomes |
| `js/timecycle.js` | 3840 | Cyclic day clock, five phases, interpolated sky colours and light, clock labels |
| `js/camera.js` | 1808 | Follow with exponential easing, world-bound clamp on both axes, reduced-motion snap |
| `tests/terrain.test.js` | 7059 | 16 terrain, serialization, bounds and noise tests |
| `tests/physics.test.js` | 4597 | 10 gravity, movement, jump, wall, ceiling, tunnelling and bounds tests |
| `tests/interaction.test.js` | 6223 | 15 mining/placement, reach, overlap and support tests |
| `tests/inventory.test.js` | 2673 | 7 inventory tests |
| `tests/persistence.test.js` | 4084 | 9 save/load, corruption, version and storage-failure tests |
| `tests/timecycle.test.js` | 2457 | 8 clock, phase, light and colour tests |
| `tests/camera.test.js` | 2598 | 6 follow and clamp tests |
| `tests/integration.test.js` | 4528 | 5 mine-place-move-save-reload journeys at module level |

`tests/world.test.js` was not modified: all six seed tests remain byte-for-byte as shipped and pass.

### Commands and outcomes

```console
node --test "tests/**/*.test.js"
# tests 82, pass 82, fail 0  (6 seed + 76 new)

python tools/page_check.py
# static checks: ok (no missing element, no external reference)
# canvas colour buckets: 19 (>= 12)
# status marker: FAILED with red pixel (231, 76, 60)
```

The page-check failure is an expected interim state of the unit boundary, not a regression in the
simulation: `index.html` still loads only the seed script list and does not yet include
`js/rng.js`/`js/inventory.js`/`js/interaction.js`/`js/persistence.js`/`js/timecycle.js`/`js/camera.js`,
so `SandboxWorld` throws the explicit "SandboxRng is required" error at boot and `#status` turns red.
IU2 owns `index.html` and the boot wiring, and its acceptance re-runs both commands until green.

### Convention accounting (bridge rules)

| Rule | Status |
| --- | --- |
| English code/comments | followed |
| UTF-8 with LF | followed (files written as UTF-8 text) |
| No project Git commit | followed; no commit created (project is not a Git worktree; the workshop worktree holds only the untracked work order) |
| No build step; `file://` runnable | followed (classic scripts, UMD, no modules/bundler) |
| No third-party or network assets | followed (stdlib only) |
| Two-space JavaScript, existing UMD module style | followed |
| Node-loadable modules | followed (all logic modules require-able; no DOM access in IU1 modules) |
| Keep `#status` contract and layout | untouched by this unit; IU2 preserves it |
| Keep seed tests, add coverage | followed: `world.test.js` untouched, 76 tests added |
| Verification commands as declared | `node --test` run; `page_check` run and its interim failure recorded, not claimed as a pass |

No C3 de-facto rule was treated as mandatory; the existing module style was copied for consistency
only, as the discovery record permits.

### Focused verification detail

- Determinism: identical byte arrays for the same seed, different arrays for a different seed.
- Seed contract: grass at (10,41), dirt at (10,42), stone at (10,63), air at (10,0), plateau exactly
  flat for four seeds including 0 and 1337.
- Physics: no wall penetration, no ceiling penetration, no tunnelling at 1000 tiles/s, delta clamp at
  large frame gaps, world-bound clamp.
- Interaction: every refusal path is covered and asserts the world is unchanged; successful mining and
  placement adjust the world and counts exactly once.
- Persistence: full round-trip, empty/corrupt/version/unavailable outcomes, selection validation and
  time normalization.
- Integration: mine → placement → movement → save → reload preserves world, position and counts.

## Findings

- The simulation boundary is coherent: pure modules, no DOM, no hidden state, deterministic outputs.
- The only interim failure is the un-wired page boot described above; it is owned and re-verified by
  IU2 and is not accepted as a final state.
- `world.surfaces` is a generation-time helper only; it is not serialized, and consumers that need the
  original terrain height use `surfaceHeightAt(seed, x)`, so later mining cannot desynchronise it.

## Conclusion

IU1 is complete and its focused verification is green (82/82 tests). Residual work delegated to IU2:
wire the new modules into `index.html`, implement presentation/UI/audio/main, complete the remaining
test suites, run `page_check` and the browser journey probe, and iterate the 960x600 visual result.
