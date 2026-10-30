---
schema_version: 1
document_kind: work-order-solution
content_language: en
work_order_id: "20261030-0000-minecraft-sandbox"
feature_ids: []
orchestration:
  main_tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261030-0000-minecraft-sandbox\\runtime\\orchestration.xml"
---

# Solution — 2D Minecraft-style sandbox

## Selected change

Build the requested sandbox as a modular static page in `project/`, preserving the seed's UMD-style
browser modules and its two verification commands. The architecture is a single canvas renderer with
a DOM overlay, deterministic seeded world generation, AABB player physics, block interaction with an
inventory-backed nine-slot hotbar, a clamped smooth camera, versioned `localStorage` persistence,
procedural audio, a continuous day/night clock, pause, reduced-motion support, 1280-wide scaling,
numeric seed entry and live coordinates.

Implementation units:

- **U1 — Seeded world generation.** `js/rng.js` (string/number hashing, mulberry32 PRNG, seed
  parsing/clamping), `js/world.js` (layered height field with a flat spawn plateau, grass/dirt/
  stone/sand strata, cave pockets, deterministic trees, bounded block access, serialization),
  `js/config.js` (seed, block registry, hotbar stock, physics and savable defaults).
- **U2 — Physics and camera.** `js/player.js` (gravity, run, jump, axis-separated AABB collision,
  spawn/respawn), `js/camera.js` (smooth follow with world-bound clamping and viewport math).
- **U3 — Interaction and inventory.** `js/interaction.js` (cursor-to-block targeting, reach and
  adjacency validation, mining progress, placement refusal rules, per-block counts, hotbar
  selection by number key and wheel).
- **U4 — Persistence and settings.** `js/storage.js` (versioned payload save/load, defensive
  validation, corrupt-payload recovery, settings round-trip with an injectable storage for tests).
  `js/daynight.js` (clock advance, palette interpolation, phase labels, sky/light computation).
- **U5 — Presentation, feedback and shell.** `js/render.js` (pre-rendered textured tile variants,
  parallax sky/hills/clouds, sun/moon/stars, depth shading, hover/crack overlays, particles, blocky
  player sprite with walk/jump/mine poses), `js/audio.js` (procedural WebAudio SFX and mute),
  `js/ui.js` (HUD formatting, seed-input parsing, key map, toast model, reduced-motion detection),
  `js/main.js` (boot, loop, input wiring, autosave, pause, seed regeneration, status marker),
  `index.html` (accessible shell with HUD, nine-slot hotbar, seed panel, help/pause overlays,
  toasts), `css/style.css` (visual design, 1280-wide scaling, reduced-motion rules), `README.md`
  (what the page is, controls, checks, architecture).
- **U6 — Verification suite.** `tests/` gains focused suites for generation, physics, camera,
  interaction, storage, day/night, audio, UI/model helpers, render helpers and the static shell;
  the six seed tests stay untouched. `tools/page_check.py` is used unchanged.

Implementation sequence: U1 → U2 → U3+U4 → U5 → verification. U5 depends on the model modules, so it
is implemented last; every unit ships its focused tests in the same node.

### Scope decision

| Field | Value |
| --- | --- |
| Task type | `create` |
| Minimality strength | none — the goal explicitly sets the quality bar above the literal checklist |
| Chosen scope | the full requested experience + all twelve prior accepted capabilities + the accepted signature shoulds (S1-S5) |
| Release or promotion trigger | none; the deliverable is the static page itself, verified in place |
| User confirmation reference | No user is available. The main-session `approve-work-order-solution` gate records the decision; no material `goal-authored` exclusion exists to confirm (analysis records "no material exclusions") |
| Implementation boundary | files under `project/` (HTML, CSS, JS, tests, README). No build tooling, no dependencies, no network, no project Git commit, no feature directory, no workshop document outside the work order |

## Accepted capability matrix

Every must and should capability from `analysis.md` is covered; none is deferred, and no capability
is dropped between analysis and this solution.

| Capability | Priority | Implementation unit | Verification |
| --- | --- | --- | --- |
| M1 Seed-driven terrain with grass, dirt, stone, height variety and trees | must | U1 `rng.js` / `world.js` | `tests/generation.test.js`, `tests/rng.test.js`; before/after screenshots |
| M2 Gravity, movement, jumping, solid collision | must | U2 `player.js` | `tests/player.test.js`; browser boot check |
| M3 Mining within reach with feedback | must | U3 `interaction.js` + U5 `render.js` crack/particles | `tests/interaction.test.js`; visual review |
| M4 Placement in empty adjacent cell, never inside the player | must | U3 `interaction.js` | `tests/interaction.test.js` |
| M5 Hotbar >= 4 types, number keys, visible selection | must | U3 `interaction.js` + U5 `index.html`/`main.js`/`ui.js` | `tests/interaction.test.js`, `tests/ui.test.js`, `tests/shell.test.js`; screenshot |
| M6 Camera follows and stays in bounds | must | U2 `camera.js` | `tests/camera.test.js` |
| M7 localStorage save/restore | must | U4 `storage.js` + U5 `main.js` autosave | `tests/storage.test.js`; browser boot |
| M8 Offline delivery, no network, status marker | must | U5 `index.html`/`main.js`/`css` | `python tools/page_check.py`; `tests/shell.test.js` |
| M9 Clean readable code and controls note | must | U5 `README.md` and module layout | README inspection; independent review |
| M10 Suite >= 52 tests including six seed tests | must | U6 `tests/` | `node --test "tests/**/*.test.js"` |
| M11 Nine slots with per-block counts | must | U3 `interaction.js` + U5 HUD/hotbar | `tests/interaction.test.js`, `tests/shell.test.js`; screenshot |
| M12 Numeric seed entry | must | U1 seed helpers + U5 seed panel | `tests/ui.test.js`, `tests/rng.test.js`; browser check |
| M13 Day/night cycle | must | U4 `daynight.js` + U5 render/HUD | `tests/daynight.test.js`; day and night screenshots |
| M14 Pause | must | U5 `main.js` + `ui.js` + overlays | `tests/ui.test.js`; pause screenshot |
| M15 Procedural audio and mute | must | U5 `audio.js` + mute control | `tests/audio.test.js`; browser boot |
| M16 Reduced-motion support | must | U5 `css/style.css` + `ui.js` + `render.js` | `tests/ui.test.js`, `tests/shell.test.js`; forced-reduced-motion screenshot |
| M17 Wheel selection | must | U3 `interaction.js` | `tests/interaction.test.js` |
| M18 1280-wide scaling | must | U5 `css/style.css` media query | `tests/shell.test.js`; 1280-wide screenshot |
| M19 Coordinates | must | U5 `ui.js` + HUD | `tests/ui.test.js`; screenshot |
| M20 Eighth hotbar block | must | U1 block registry + U3 hotbar model | `tests/interaction.test.js`, `tests/shell.test.js` |
| S1 Hover outline, mining crack stages, particles | should | U5 `render.js` + U3 mining progress | `tests/render.test.js`; visual review |
| S2 Distinct procedural sound design | should | U5 `audio.js` | `tests/audio.test.js`; browser boot |
| S3 Parallax hills/clouds, textured tiles, depth shading, caves, trees | should | U5 `render.js` + U1 generation | `tests/render.test.js`, `tests/generation.test.js`; screenshots |
| S4 Help panel, toasts, pause overlay, hover block info | should | U5 `ui.js`, `index.html`, `main.js` | `tests/ui.test.js`; screenshots; visual review |
| S5 In-page controls note | should | U5 `index.html` help panel + `README.md` | `tests/ui.test.js`; visual review |

### Prior capability dispositions carried into the solution

| Prior capability | Disposition | Implementation | Verification |
| --- | --- | --- | --- |
| P1 Per-block inventory counts | improve | U3 counts model + U5 slot counts | `tests/interaction.test.js`, `tests/shell.test.js` |
| P2 52 tests including seed tests | preserve | U6 suite, seed file untouched | `node --test` count/exit |
| P3 Reduced-motion support | improve | U5 CSS + JS detection | `tests/ui.test.js`, `tests/shell.test.js`, forced-motion screenshot |
| P4 Wheel selection | preserve | U3 wheel cycling | `tests/interaction.test.js` |
| P5 1280-wide scaling | preserve | U5 media query | `tests/shell.test.js`, 1280 screenshot |
| P6 Audio/mute | improve | U5 `audio.js` + persisted mute | `tests/audio.test.js`, `tests/storage.test.js` |
| P7 Numeric seed entry | improve | U1 parsing + U5 seed panel | `tests/ui.test.js`, `tests/rng.test.js` |
| P8 Pause | improve | U5 pause state/overlay | `tests/ui.test.js`; screenshot |
| P9 Eighth hotbar block | preserve | U1 registry, slot 8 cobblestone | `tests/interaction.test.js`, `tests/shell.test.js` |
| P10 Day/night | improve | U4 clock + U5 sky/light/HUD | `tests/daynight.test.js`; screenshots |
| P11 Nine-slot hotbar | preserve | U5 shell + U3 model | `tests/shell.test.js`, `tests/interaction.test.js` |
| P12 Coordinates | improve | U5 HUD formatter | `tests/ui.test.js`; screenshot |

No prior item is replaced, retired or deferred, so no independence question about a replace/retire
source arises. A wholly undispositioned item would block this gate; none is missing.

### Version disposition

The project bridge declares no version policy. Recording that fact: there is no version scheme,
release ladder or bump trigger to apply, so `js/config.js` keeps its existing `version` value and no
version change is made. Decision status: recorded; actor: main session (no user available); date:
2026-10-30. This record does not authorize any release, tag or publication.

## Feature baseline impact

`feature_ids=[]`; no managed feature exists and none is created. There is no feature baseline to
synchronize, and this work order does not modify any feature document. No project Git commit is
created, by project bridge and by explicit run instruction.

## Implementation and migration strategy

- Keep the existing module wrapper style (UMD-style, Node-requireable) and two-space indentation.
- Extend `config.js` rather than replacing its public fields the seed tests read; add the block
  registry, hotbar order, starter stock and defaults alongside the existing constants.
- Keep `world.js`'s public functions and serialization shape; layer the new generator on top so the
  six seed tests keep passing unchanged. The spawn plateau keeps column 10 flat at
  `floor(height * 0.65)`.
- Replace the placeholder `player.js` step with real physics while keeping `createPlayer` and the
  `stepPlayer(player, world, input, dt)` entry point.
- Replace `render.js` and `main.js` internals; both stay free of network references and Node-safe at
  require time (canvas/DOM touched only inside called functions).
- Add the new modules rather than growing one file; each module exports pure functions that tests can
  exercise without a DOM.
- Update `index.html` and `css/style.css` for the accessible shell, scaling and reduced motion; keep
  the required ids `game`, `status`, `hud`, `hotbar` and the `booting`/`ready`/`error` contract.
- Rewrite `README.md` to describe the game, controls, checks and architecture.
- No migration of existing data is required: the save payload gains a schema version and readers
  tolerate older/absent data by falling back to a fresh world.

## Verification strategy

1. `node --test "tests/**/*.test.js"` — must pass with at least 52 tests, including the untouched
   six seed tests; suites map to every capability row above.
2. `python tools/page_check.py` — static asset/network checks, boot to `ready`, status-marker pixel,
   non-blank canvas; rerun with `--screenshot` under the workbench `tmp/`.
3. Browser evidence at three states: default 960x600, 1280-wide (scaling media query), and forced
   reduced motion; screenshots are inspected against the quality contract and kept under the
   workbench `tmp/` unless promoted as review evidence.
4. Capability-to-evidence mapping is recorded in the verification artifact: every must/should row is
   either proven by a named test/command or explicitly recorded as an evidence gap.
5. Independent visual review of the final page (rendered screenshots plus the page itself); every
   required finding is fixed with a repair node and re-verified before the result document.
