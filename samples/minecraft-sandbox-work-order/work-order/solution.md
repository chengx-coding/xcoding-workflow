---
schema_version: 1
document_kind: work-order-solution
content_language: en
work_order_id: "20261030-1819-mc-2d-sandbox"
feature_ids: []
orchestration:
  main_tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Solution: accepted capability matrix and implementation plan

## Selected change

### Scope decision

- **Task type:** `create`.
- **Minimality strength:** none. The goal has no minimality presumption; the chosen scope is the
  smallest coherent implementation that delivers the whole accepted capability matrix at the quality
  bar, not the smallest possible patch.
- **Chosen scope:** the consumer project's static page surface — `index.html`, `css/style.css`,
  `js/*`, `tests/*`, `tools/` (page check kept, one new automated journey probe), and `README.md`.
  The seed's module boundary, UMD load pattern, status-marker contract and verification commands are
  preserved.
- **Out of scope (sourced):** no network/multiplayer, no third-party libraries/CDN/fonts, no build step
  or server requirement, no project Git commit, no change report. Sources are the request, the
  `.xcoding/WORKFLOW.md` bridge, and the user's explicit decisions.
- **Release and promotion triggers:** none. This is a sample page with no release process and the
  bridge declares no version policy; nothing is published and no version source is changed. The
  internal `config.version` is a payload marker, not a release version, and stays unchanged.
- **User confirmation reference:** the initiating prompt and its binding decisions (standard create
  lifecycle, quality contract, independent visual review, report waiver, no commit, no user gate). No
  user is available, so the solution gate is completed by the main session with recorded reasoning.
- **Implementation boundary:** product files under `C:\dev\xcoding-workflow-dev\wf-iterations\0.3.8\project\`
  only; all temporary scripts, screenshots, logs and probe output go under this work order's `tmp/`;
  the runtime XML and other managed orchestration files are never touched directly.

### Architecture

Keep the seed's UMD module style (a factory returning a public API object, two-space indentation) and
extend it with focused modules so the logic stays Node-loadable without a DOM:

| Module | Responsibility |
| --- | --- |
| `js/config.js` | Constants: block catalogue (9 types with palette, hardness, solidity), hotbar order, world/tile size, physics, reach, time-of-day, save key/version, starter kit |
| `js/rng.js` | Deterministic seeded PRNG (mulberry32) and value-noise helpers used by terrain |
| `js/world.js` | `createWorld(seed)` (heightmap, layers, spawn plateau, trees, sand, caves), bounded `getBlock`/`setBlock`, `isSolid`, counts, serialize/deserialize |
| `js/player.js` | Player state and axis-separated AABB physics with sub-stepping, jump and grounding |
| `js/inventory.js` | Per-block counts, add/consume, serialization, never-negative invariant |
| `js/interaction.js` | Mining and placement rules with structured `{ok, reason, block}` results and player-overlap protection |
| `js/persistence.js` | Versioned payload, storage adapter (localStorage or in-memory), corruption fallback |
| `js/timecycle.js` | Clock, phases (dawn/day/dusk/night), sky/light values, labels |
| `js/camera.js` | Follow with easing and world-bound clamping |
| `js/render.js` | Canvas 2D world/background/player/particles/highlight, day-night sky and light, recording-context friendly |
| `js/ui.js` | Hotbar DOM, HUD text, toasts, pause overlay, seed form, mute state; pure formatting helpers tested in Node |
| `js/audio.js` | Lazy WebAudio tones for mine/place/jump/select with mute |
| `js/main.js` | Boot, input, loop, save triggers, status marker, `window.__sandbox` probe surface |

Terrain: seeded value noise over an exact flat spawn plateau — columns 0 through 24 inclusive are flat
at base surface row 41 (preserving the seed test that pins grass at (10, 41), dirt at (10, 42) and
stone at (10, 63)); column 25 and column 26 are a deterministic two-column blend from 41 to the noise
height, and columns 27–127 use the seeded noise heightmap clamped to rows 33–46. Surface is grass,
three to four rows of dirt follow, then stone to row 63, with sand patches on low flats, deterministic
trees above the surface (trunk wood plus a leaves canopy) and carved caves below the surface that never
touch rows 62–63. The player spawns on the plateau at column 12. World is 128x64 tiles at 32 px
(4096x2048 px) so the camera clamp is meaningful on both axes.

Block palette (exact order, keys 1–9): `grass`, `dirt`, `stone`, `wood`, `leaves`, `sand`, `planks`,
`glass`, `brick` — nine block ids in that order, one per hotbar slot, each with its own palette colour.
Terrain generates grass, dirt, stone, wood, leaves and sand; planks, glass and brick are build-only
palette blocks supplied by the starter kit. The eighth hotbar block is `glass` in slot 8; the ninth is
`brick` in slot 9.

Resource model (resolves the analysis's open decision): mining adds one block of the mined type;
placement consumes one. The exact starter kit is grass 16, dirt 24, stone 16, wood 8, leaves 0, sand 8,
planks 12, glass 8, brick 12 — leaves deliberately start at zero so the empty-inventory refusal (J5)
is reachable without any special setup, while every other slot is immediately usable. Refusals name the
reason (`That spot is not empty`, `You are standing there`, `Build next to a block`, `Out of reach`,
`No <block> left - mine some first`). This preserves per-block counts as a real mechanic and gives the
required refusal explanation both a world-integrity case and an empty-inventory case.

Feedback: hovered-tile highlight with corner ticks, dust burst on mine, puff on place, toast line,
selected slot ring, sound, and a paused overlay. Day/night drives the sky, a sun/moon arc, stars,
ambient darkness with a player light, and the clock badge.

Persistence: `localStorage` key `xc-sandbox-sample-v2`; payload `{v, seed, time, selected, player
{x,y}, inventory, world {w,h,blocks:[[block,count],...]}}` with RLE blocks. Save after mine/place,
every few seconds when state changed, on pause, and on `pagehide`; load before the first frame. An
unreadable payload produces a fresh world and a visible notice, never a red error state.

### Accepted capability matrix

`IU1` = simulation implementation unit; `IU2` = experience/presentation implementation unit;
`V1` = automated logic tests; `V2` = `tools/page_check.py` + screenshot; `V3` = automated journey probe;
`V4` = independent visual review and M2D-SES v1.1 score.

| # | Capability | Priority | Implementation unit | Verification |
| --- | --- | --- | --- | --- |
| C1 | Deterministic seeded terrain (grass/dirt/stone) | must | IU1 world/rng/config | V1 determinism + layer tests; V2 seeded page; V3 seed compare |
| C2 | Movement, gravity, jump, solid collision | must | IU1 player/config | V1 physics tests; V3 movement/jump probe |
| C3 | Left-click mining within reach | must | IU1 interaction + IU2 input | V1 interaction tests; V3 click probe |
| C4 | Right-click placement, player protection, refusal text | must | IU1 interaction/inventory + IU2 toast | V1 placement tests; V3 refusal probes |
| C5 | Hotbar ≥4 types, number keys, selected state | must | IU2 ui/config | V1 UI tests; V3 key/wheel probe |
| C6 | Camera follow and world-bound clamp | must | IU1 camera + IU2 main | V1 camera tests; V3 boundary probe |
| C7 | localStorage save/load restored on load | must | IU1 persistence + IU2 main | V1 persistence tests; V3 reload probe |
| C8 | Readable page, hint line, offline `file://` | must | IU2 index/css/ui | V2 static check; V4 visual review |
| C9 | README built/run/controls/tests | must | IU2 README | V4 document review |
| C10 | `#status` marker contract | must | IU2 main/css | V2 marker pixel; V3 error-state probe |
| C11 | Tests ≥52, seed tests unchanged, required coverage | must | IU1 + IU2 tests | V1 full suite; seed file unchanged |
| C12 | No external libraries/CDN/fonts/network | must | IU2 index/css/js | V2 static network check |
| C13 | 960x600 screenshot, independent visual review, fixes | must | IU2 + review node | V2 screenshot; V4 review artifact + score |
| C14 | Standard lifecycle stages recorded | must | main session | runtime stages + validated documents |
| C15 | Per-block inventory counts | must | IU1 inventory + IU2 hotbar | V1 inventory tests; V3 badge probes |
| C16 | 52 automated tests including seed tests | must | IU1 + IU2 tests | V1 suite count ≥52 |
| C17 | Reduced-motion support | should | IU2 css/main | V1 matchMedia test; CSS check |
| C18 | Wheel selection | should | IU2 main/ui | V1 UI test; V3 wheel probe |
| C19 | 1280-wide scaling | should | IU2 css | V2 1280x800 screenshot; CSS check |
| C20 | Audio and mute | should | IU2 audio/ui | V1 audio test; V3 mute probe |
| C21 | Numeric seed entry | should | IU2 ui/main | V1 UI test; V3 seed probe |
| C22 | Pause | should | IU2 main/ui | V1 state test; V3 two-state probe |
| C23 | Eighth hotbar block | should | IU1 config | V1 config test |
| C24 | Day/night | should | IU1 timecycle + IU2 render | V1 time tests; V3 two screenshots |
| C25 | Nine-slot hotbar | should | IU2 ui | V1 UI test; V3 visual probe |
| C26 | Coordinates | should | IU2 ui/main | V1 format test; V3 HUD probe |
| N1–N5 | Sourced non-goals | non-goal | — | Verified absent: no network, no build, no commit, no report |

Every must capability has an implementation unit and verification evidence. No should capability is
deferred; each is covered by the same two implementation units. The signature musts (immediate
feedback, palette identity, atmosphere, seed variety, persistence trust) and the signature should
(sound with mute) are covered by IU1/IU2 and by V3/V4 respectively.

### Prior capability dispositions carried into the matrix

| Prior capability | Disposition | Implementation unit | Verification |
| --- | --- | --- | --- |
| per-block inventory counts | improve | IU1 inventory, IU2 hotbar | inventory tests + badge probes |
| 52 automated tests incl. seed tests | improve | IU1 + IU2 tests | suite count + seed file unchanged |
| reduced-motion support | preserve | IU2 css/main | matchMedia test + CSS |
| wheel selection | preserve | IU2 main | UI test + wheel probe |
| 1280-wide scaling | preserve | IU2 css | 1280x800 screenshot |
| audio/mute | preserve | IU2 audio/ui | audio test + mute probe |
| numeric seed entry | preserve | IU2 ui/main | UI test + seed probe |
| pause | preserve | IU2 main/ui | state test + two-state probe |
| eighth hotbar block | preserve | IU1 config | config test |
| day/night | improve | IU1 timecycle, IU2 render | time tests + two screenshots |
| nine-slot hotbar | preserve | IU2 ui | UI test + visual probe |
| coordinates | preserve | IU2 ui/main | format test + HUD probe |

No replace, retire or defer disposition exists, so no source/impact obligation is triggered.

## Feature baseline impact

No managed features exist (`feature_ids=[]`), so no feature baseline is created, adopted or modified.
The work order is an ordinary create work order and does not implicitly create
`.xcoding/features/<feature-id>/`. Code is the only behaviour source for this page; there is no
feature contract to reconcile against.

## Implementation and migration strategy

Two sequential implementation nodes under `implementation-group`:

1. **IU1 — simulation core** (`js/config.js`, `js/rng.js`, `js/world.js`, `js/player.js`,
   `js/inventory.js`, `js/interaction.js`, `js/persistence.js`, `js/timecycle.js`, `js/camera.js` and
   their tests). Implements seeded terrain, physics/collision, interaction rules, inventory,
   persistence, clock and camera as pure modules; runs focused `node --test` on the new suites and
   confirms the six seed tests still pass. The spawn plateau is a deliberate design constraint that
   keeps the seed tests valid.
2. **IU2 — experience and presentation** (`index.html`, `css/style.css`, `js/render.js`, `js/ui.js`,
   `js/audio.js`, `js/main.js`, remaining tests, `README.md`, journey probe tool). Wires the UI, the
   canvas presentation, input, sound, pause, seed form, hotbar, coordinates, save triggers, status
   marker and the README; completes the test suite to ≥52; renders and iterates the 960x600 page.

No migration is needed: the seed has no persisted user data and its placeholder modules are replaced
in place. Existing seed tests are preserved unchanged. No external side effects, no dependency
installation, no commit.

Risks carried from analysis and their controls: seed-test compatibility is protected by the spawn
plateau; `file://` storage is verified by the reload probe with a visible fallback; audio fails silent
until a gesture; screenshot probes use stable anchors with tolerance; `window.__sandbox` stays a thin
probe surface.

## Verification strategy

1. `node --test "tests/**/*.test.js"` — full suite ≥52 tests, six seed tests unchanged, covering
   terrain determinism, block bounds, collision, placement rules and persistence.
2. `python tools/page_check.py` — static network/element checks, `ready` marker pixel and non-blank
   canvas; capture a 960x600 screenshot under this work order's `tmp/` and inspect it.
3. Automated journey probe (`tools/journey_check.js`, Node + headless Chrome DevTools Protocol) —
   executes J1–J11: mining/placement and refusal toasts, reload persistence, corrupt-save recovery,
   pause two-state, day/night two-state screenshots, boundary clamp, hotbar selection; records
   before/after observables and pixel assertions.
4. A 1280x800 render for the scaling capability, inspected.
5. Independent visual review through `xc-review` over the rendered page and implementation, scored
   against M2D-SES v1.1; every required finding fixed and re-checked before the result document.
6. Runtime/lifecycle evidence: validated documents, node artifacts, and the finalizer's source checks.

Gate plan: `approve-work-order-solution` is completed by the main session with `approved` and a
decision that records the reasoning, the accepted matrix, the all-must coverage, the prior-inventory
dispositions, the report waiver and the no-commit rule. No user is available; no question is asked.

### Revision record

- Revision 1: initial accepted matrix and plan.
- Revision 2 (review round 1, findings R1–R3): specified the exact starter-kit counts (leaves at zero),
  the ordered nine-block palette with keys and generated-vs-build-only classification, and the exact
  spawn plateau columns and base surface row.

