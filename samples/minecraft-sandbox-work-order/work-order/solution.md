---
schema_version: 1
document_kind: work-order-solution
content_language: "en"
work_order_id: "20261029-1459-2d-sandbox-game"
feature_ids: []
orchestration:
  main_tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\runtime\\orchestration.xml"
---

# Solution — a complete, distinctive offline sandbox

## Selected change

The selected change is **Option B** from the analysis: keep the seed's module split and seed-test
invariants, and build the full game loop with a deliberately authored presentation.

### World and simulation

- `js/config.js` becomes the single tuning and palette module: tile/view/world dimensions, physics
  constants in tiles per second, reach, save key, eight block ids (air, grass, dirt, stone, wood,
  leaves, sand, planks), block display names, and per-block palette/texture descriptors.
- `js/world.js` gains a `mulberry32` seed PRNG, a `(x - 10)`-zero-crossing surface wave, layered
  dirt/stone fill, deterministic trees, caves and ore speckles, and grass/flower decoration data.
  It keeps `getBlock`, `setBlock`, `isSolid`, `serializeWorld`, and `deserializeWorld` API-compatible,
  and adds `surfaceHeightAt`, `hasSolidNeighbour`, `cellWithinReach`, `rectOverlapsSolid`, and
  `canPlaceBlock` so the placement rules are testable without a DOM.
- `js/player.js` gains AABB collision with solid tiles, gravity, walking, jumping with coyote time,
  a step accumulator, facing/animation state, and `serializePlayer`/`restorePlayer`.
- `js/save.js` (new) owns a guarded `localStorage` adapter with an in-memory fallback, versioned save
  payloads, `saveGame`/`loadGame`/`clearGame`, and validation that rejects corrupt or foreign data.

### Presentation and interaction

- `js/render.js` gains a full-frame renderer: layered sky gradient, sun glow, drifting clouds,
  parallax ridges, procedural per-block textures cached in offscreen canvases, ambient occlusion at
  exposed edges, grass/flower overlays, a smooth clamped camera with look-ahead, a character with
  helmet/scarf/limbs/lantern, a pulsing reach/mine outline, ghost placement preview, break particles
  and screen vignette.
- `js/main.js` becomes the app controller: full-window DPR-aware canvas sizing, fixed-step game loop,
  keyboard/mouse input, hotbar state (1–8 and wheel), mine/place actions with cooldown, particle and
  toast events, HUD/seed/save/pause wiring, synthesized WebAudio feedback (mute toggle), coalesced
  autosave and save-on-pagehide, world reset with a new seed, help/pause overlay, and the `#status`
  booting → ready/error contract.
- `index.html` and `css/style.css` are rebuilt around a full-window canvas plus layered HUD panels:
  brand/seed chip, save state, control hints, a large eight-slot hotbar with swatches and names, a
  toast rail, and a help/pause dialog. `#status` stays a 14px bottom-left dot with a green ready state
  so `page_check.py` still reads it.

### Preserved contracts

- `#game`, `#hud`, `#hotbar`, `#status` ids remain, as do the UMD module wrappers and the classic
  script order.
- Every seed assertion holds: surface at column 10 equals the base ground row, dirt below it, stone at
  the bottom row, air at the top, and bounded block access.
- No external references, no fonts, no network calls. Save data never leaves the machine.

## Scope decision

- **Task type:** create.
- **Minimality strength:** none. Create maximizes user value within the constraints and the quality
  bar rather than minimizing the diff.
- **Chosen scope:** the whole page and its modules, tests and README. `tools/page_check.py` is not
  expected to change; if a legitimate verification need appears it may be extended without weakening
  existing checks.
- **Implementation boundary:** `project/index.html`, `project/css/style.css`, `project/js/*.js`,
  `project/tests/*.js`, `project/README.md`. Excluded: mobs, combat, crafting, multiplayer, external
  assets, build tooling, feature baselines, and any change outside `project/`.
- **Release/promotion triggers:** not applicable to this offline sample. Promotion is the quality bar
  plus the pass of both project checks and the independent visual review.
- **User confirmation reference:** no user is available in this run. The binding instruction requires
  the main session to complete the solution gate itself with a concrete decision; that decision and
  this boundary are the approval record.
- **Version policy:** the project bridge declares no version policy and no version source is part of
  the delivered surface. No version bump is invented; the existing `config.version` stays as the
  seed's 0.1.0 and the result records the no-policy fact.
- **Commit policy:** the bridge forbids a project Git commit. The work order leaves the commit to the
  enclosing `xcoding-workflow` repository and records that decision in the result.

## Feature baseline impact

`feature_ids=[]` and no managed feature exists, so there is no baseline to update or reconcile. The
seed tests and the `#status`/module contracts are the de facto baseline this create work must preserve;
the new tests extend coverage rather than weakening it.

## Implementation and migration strategy

The work is additive and ordered so each layer can be verified before the next depends on it.

| Unit | Files | Content | Proof |
| --- | --- | --- | --- |
| IU1 — core simulation | `js/config.js`, `js/world.js`, `js/player.js` | constants, seeded terrain, collision, physics, placement rules | new Node unit tests |
| IU2 — persistence | `js/save.js` | guarded storage, versioned payloads, fallback | new Node unit tests with fake storage |
| IU3 — presentation | `js/render.js`, `css/style.css` | sky, parallax, textures, camera, character, effects, HUD layout | screenshot inspection |
| IU4 — app shell | `index.html`, `js/main.js`, `README.md` | boot, loop, input, hotbar, HUD, audio, pause/help, autosave, documentation | page check + screenshots |
| IU5 — verification & polish | `tests/*.test.js`, presentation tuning | regression coverage, visual iteration, independent review, fixes | both checks + review evidence |

Migration is a rewrite of the seed's placeholder internals behind stable module boundaries: the UMD
factory shape, the exported function names used by the tests, and the DOM ids remain recognisable, so
the page and the tests can be reasoned about as one continuous project rather than a replacement.

## Verification strategy

1. **Logic:** `node --test "tests/**/*.test.js"` must pass the six unchanged seed tests plus new tests
   for seed determinism, the column-10 invariant for a second seed, collision on all axes, jump
   availability, reach/adjacency/player-overlap placement rules, and save/load round-trips (including
   corrupt-payload rejection and the memory fallback).
2. **Static and runtime page check:** `python tools/page_check.py` must report no external references,
   all local assets present, the ready marker pixel, and a non-blank canvas.
3. **Rendered inspection:** capture headless screenshots at desktop and narrow viewports under the
   work-order `tmp/` directory, inspect them visually, compare against the quality bar, and iterate on
   hierarchy, contrast, density and feedback.
4. **Independent visual review:** a reviewer that did not author the page renders the final page,
   inspects the screenshot, and records required findings and non-blocking observations against the
   quality contract. Every required finding is fixed and re-checked before the result document.
5. **Residual risk record:** the result records unexecuted checks, storage caveats, and the no-commit
   decision.
