---
schema_version: 1
document_kind: work-order-analysis
content_language: en
work_order_id: 20261102-1145-open-sandbox-xc-044
feature_ids: []
orchestration:
  main_tree_ref: .xcoding/work-orders/20261102-1145-open-sandbox-xc-044/runtime/orchestration.xml
---

# Analysis — what this small Minecraft must be

## Confirmed facts

- The seed renders an offline placeholder world and already owns a unit-test contract
  (`tests/world.test.js`, 6 tests) and a browser contract (`tools/page_check.py`) that must not be
  weakened. `page_check` fixes four element ids (`game`, `status`, `hud`, `hotbar`), a green
  bottom-left status marker, a network-reference scan over page-served files, and a ≥12-colour-bucket
  canvas check.
- Four probes in headless Chrome from `file://` (`tmp/probe.html`, `--dump-dom
  --virtual-time-budget=2000`) confirmed: `localStorage` is writable, Canvas 2D works exactly,
  `AudioContext` exists, `devicePixelRatio=1`, default headless viewport `762×484`.
- The bridge waives the change report (`user_waived`), forbids a project Git commit, requires
  English/UTF-8/LF, keeps verification at `node --test "tests/**/*.test.js"` and
  `python tools/page_check.py`, and confines process files to the workbench `tmp/`.
- No prior accepted capability inventory exists for this product, so preservation disposition is
  **not applicable**; no feature IDs are associated.
- Detailed evidence, trade-off text and the browser probe record are in
  `artifacts/analysis-evidence.md`.

## Scope assessment

Task type is `create`: there is no minimality presumption. The binding scope comes from the user
prompt (2D, offline, `file://`, no build/libraries/CDN/network, small Minecraft, save progress,
document controls) and from the applied experience requirements (first-run affordance, visual-state
backdrop, discoverability/visual-review/progression lens). The seed is a shell, not an existing
product, so this is a build, not a repair. The only narrowing is the deferral of reference systems
the request is silent about; each is recorded below with impact and a reversal path and none is
declared forbidden.

## Capability map (canonical)

Priorities: `must` / `should` / `non-goal`. Decisions: `implement`, `defer`, `not applicable`.
Acceptance columns and per-row verification detail live in `artifacts/analysis-evidence.md`; this
table is the decision record carried into the solution.

| Capability | Source | Priority | Decision |
| --- | --- | --- | --- |
| Walk, jump, gravity, collision | user "playable" | must | implement |
| Seeded world: surface variety, caves, ores, trees | user, reference S5 | must | implement |
| Mining: hardness, tool speed, cracks, particles, drops | reference S1 | must | implement |
| Placement: reach, adjacency, no overlap | user, reference S1 | must | implement |
| Hotbar + inventory with counts | reference S1 | must | implement |
| Crafting: material → capability | reference S4 | must | implement |
| Tool tiers changing mining speed | reference S4 | must | implement |
| Day/night cycle and sky backdrop | reference S2 | must | implement |
| Skylight + torch light propagation | reference S3 | must | implement |
| Torch item craftable and placeable | reference S3 | must | implement |
| Save/load world, player, inventory, time, tasks | user "save progress" | must | implement |
| Storage-failure fallback: export/import | user, Q6 | must | implement |
| First-run affordance: welcome, buttons, tasks | user Q4 | must | implement |
| Visual-state backdrop before/after (edit/mode/time/view) | user Q5 | must | implement |
| Experience lens applied | user Q8 | must | implement |
| Controls documented in product and README | user | must | implement |
| Task chain with rewards and progress | user Q8, reference | must | implement |
| Minimap with viewport trail | user Q5 | should | implement |
| Procedural audio feedback | reference S1 | should | implement |
| Zoom controls | user Q5, comfort | should | implement |
| Backdrop inspect mode | user Q5 | should | implement |
| Custom seed / new world | reference S5 | should | implement |
| Undo/redo of edits | reference, Q5 | should | implement |
| Ambient critters | reference | should (proposed) | defer |
| Mobs and combat | reference | should (proposed) | defer |
| Hunger/food | reference | should (proposed) | defer |
| Redstone/circuits | reference | should (proposed) | defer |
| Dimensions (Nether) | reference | should (proposed) | defer |
| Furnace/workbench stations, 3×3 grid | reference | should (proposed) | defer |
| Water/lava fluid simulation | reference | should (proposed) | defer |
| Multiplayer | reference | non-goal | not applicable (offline is user-sourced) |
| 3D voxel rendering | reference | non-goal | not applicable (2D is user-sourced) |
| Touch/mobile controls | accessibility | should (proposed) | defer |

Deferral impact, recorded now so the solution can carry it: critters/mobs/combat/hunger leave the
game without survival threat; redstone leaves no automation; dimensions leave one world layer;
stations make crafting a recipe list rather than a ritual; fluids leave a static environment; touch
input assumes a keyboard and mouse. Each is reversible without rework of the world, save format, or
rendering architecture.

## Signature-experience table

Reference: Minecraft, credible because the prompt names it and its loop is the target. Evidence is
the reference's documented core loop; decisions are reference-derived, not measured here.

| Signature | Evidence | Goal covers | Decision | User value |
| --- | --- | --- | --- | --- |
| S1 Tactile break/place | mining/building loop | Q2 | must, depth on mining/placement/tools/audio | the core verb feels good |
| S2 Living cyclic world | day/night | Q2, A5 | must, depth on time/sky | pressure and atmosphere |
| S3 Darkness needs light | lighting, torches | A5 | must, depth on light and torches | caves become goals |
| S4 Gathering becomes capability | crafting, tools | A3 | must, depth on recipes/tools/tasks | visible progression |
| S5 Seed world worth exploring | world generation | A4 | must, depth on generation/new seed | replayable exploration |
| S6 Leaving and returning is safe | save/worlds | Q6, A6 | must, depth on save | trust in the world |

All six sharpen requested capabilities; none imports an unrequested system. The reduced set is used
because the request is explicitly "small".

## Design options

- **Code shape**: UMD IIFE modules per concern, loaded in order — no build, `file://` safe, and
  Node-testable like the seed. Chosen over a monolith (reviewability) and ES modules (blocked by
  `file://` CORS rules).
- **Rendering**: canvas immediate draw with procedural tile detail; DOM overlay HUD. Canvas gives
  60 fps over ~1k tiles and pixel control for ghosts; DOM gives real clickable affordances required
  by Q4 and testable focus/semantics.
- **View**: full-viewport, DPR-aware canvas, zoom 0.6–2.5×. Creates a genuine viewport-change axis
  for Q5 instead of a fixed 960×540 box.
- **Persistence**: `localStorage` primary (probe-confirmed on `file://`), auto-save plus explicit
  save, RLE-encoded world in a versioned JSON envelope, JSON export/import, in-memory fallback with
  a visible warning. Chosen over IndexedDB (async complexity) and file-only (worse default).
- **Lighting**: flood-fill skylight plus torch light, recomputed on edits and time transitions;
  measure the cost in the browser and debounce only if the measurement requires it.
- **Crafting**: recipe list with progressive unlocks and Craft buttons, chosen over a 3×3 grid and
  stations for discoverability and click-testability.
- **Day length**: 4-minute full cycle so night arrives inside a first session.
- **Backdrop**: all three layers — world ghosts for edits, a kind-labelled HUD before/after pulse
  for edit/mode/time/view, and a minimap viewport trail — because Q5 names removed/covered content
  and mode/theme/time/viewport changes separately.
- **Verification**: node logic tests, the untouched `page_check`, plus a new scripted headless-browser
  check using `--dump-dom` self-tests, paired screenshots, and a two-run persistence test.

## Risks and hypotheses

- Flood-fill relighting must stay fast enough for synchronous edits; if not, relight on a trailing
  timer without changing behaviour.
- `localStorage` may be cleared between headless launches; the two-run persistence test will settle
  it, with same-run reload evidence and export/import as fallback evidence.
- The first-run overlay must not cover the `#status` marker or starve the canvas colour check; the
  marker stays topmost and the world stays visible behind the overlay.
- Rendering cost at the largest supported viewport with the lighting overlay is unmeasured until the
  implementation exists.

## Request-to-goal comparison and unresolved decisions

The goal covers every user requirement and all three applied experience requirements; it adds no
binding exclusion. No material human-owned decision remains open: the applied Q4/Q5/Q8 requirements
are explicit, and the deferred reference systems are reversible should-items rather than exclusions.
No clarification gate is required.
