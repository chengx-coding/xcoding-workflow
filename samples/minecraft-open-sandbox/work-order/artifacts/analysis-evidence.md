---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: 20261102-1145-open-sandbox-xc-044
node_id: rt_work-order-20261102-1145-open-sandbox-xc-044__dyn-1__analysis-evidence
feature_ids: []
orchestration:
  tree_ref: .xcoding/work-orders/20261102-1145-open-sandbox-xc-044/runtime/orchestration.xml
---

# Analysis evidence — capability map, signature table, design options

## Scope and method

`analysis_scope=solution-support` for a `create` work order with no feature baselines. Evidence comes
from the seed code (`index.html`, `js/config.js`, `js/world.js`, `js/player.js`, `js/render.js`,
`js/main.js`, `css/style.css`, `tests/world.test.js`, `tools/page_check.py`), the project bridge
`.xcoding/WORKFLOW.md`, the work-order `goal.md`, the Minecraft reference, and four browser probes
run from the workbench `tmp/`. No product code was modified. A prior accepted capability inventory
was not supplied: preservation disposition is **not applicable**.

## Confirmed facts

1. The seed is a working offline shell: it boots, renders a flat 128×64 placeholder world, reports a
   page status, and is unit-tested by `tests/world.test.js` (6 tests over config, world bounds,
   serialization, solidity). `js/main.js` is browser-only; the other four modules use a UMD wrapper
   that runs under Node `require` and in the page.
2. `tools/page_check.py` is a hard acceptance surface: required ids `game`, `status`, `hud`,
   `hotbar`; the `#status` marker must be a 14×14 fixed element at the bottom-left and green
   (`#2ecc71`) in the ready state; every page-served file is scanned for `http(s)://`, `//cdn`, and
   `@import url(https:`; the canvas region of the screenshot must contain at least 12 colour
   buckets. It must not be weakened.
3. Browser probe `tmp/probe.html` (headless Chrome 143, `--virtual-time-budget=2000 --dump-dom`,
   `file://`): `localStorage` is **writable** on `file://`, Canvas 2D pixel writes are exact,
   `AudioContext` is available, `devicePixelRatio=1`, default headless viewport `762×484`.
   Consequence: browser storage is a viable primary save, and `--dump-dom` is a viable
   machine-readable browser test channel without any dependency.
4. `index.html` currently loads five scripts in order and has no external references. The status
   marker colour contract makes a full-screen first-run overlay safe only if the marker stays on top
   of it (`z-index`).
5. The bridge waives the change report (`requires_report=false`, `report_skip_reason=user_waived`),
   forbids a project Git commit, requires English/UTF-8/LF, and fixes the verification commands to
   `node --test "tests/**/*.test.js"` and `python tools/page_check.py`.
6. The seed canvas is 960×540 CSS with a 960px `#app`; nothing prevents a full-viewport canvas, and
   the seed tests do not pin the view size (only `config.viewWidth`/`viewHeight` values exist).

## Capability map

Priorities: `must` = required for the requested outcome and quality contract; `should` = strengthens
the requested experience, accepted only when affordable; `non-goal` = confirmed inapplicable. A
`defer` decision in the "Decision" column is a reversible scope decision recorded by the solution,
not an exclusion of the capability from the domain.

| # | Capability (user-observable) | Source | Priority | User value | Acceptance | Verification | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Walk, jump, gravity, AABB collision | user: "playable" | must | The game is playable at all | Lands, climbs 1-block steps, cannot pass walls | `tests/physics.test.js` + browser selftest | implement |
| 2 | Seeded world with surface variety, caves, ores, trees | user: "small Minecraft"; reference | must | A world worth exploring; reproducible | Same seed → same world; different seed → different | `tests/worldgen.test.js` + screenshot | implement |
| 3 | Mining with hardness, tool speed, cracks, particles, drops | user: "Minecraft feel"; reference signature 1 | must | Tactile core loop | Hold to break; stone slower than dirt; correct drop | `tests/mining.test.js` + browser selftest | implement |
| 4 | Placement with reach, adjacency and no-overlap rules | user: "2D sandbox"; reference signature 1 | must | Building is the second half of the loop | Cannot place inside player, beyond reach, or in mid-air | `tests/placement.test.js` + browser selftest | implement |
| 5 | Hotbar and inventory with counts | user: "Minecraft feel" | must | Managing gathered blocks | Counts add/remove; hotbar selectable | `tests/inventory.test.js` + browser click test | implement |
| 6 | Crafting that converts gathered material into capability | reference signature 4 | must | Progression from wood to tools | Recipes consume inputs, produce outputs, refuse when short | `tests/crafting.test.js` + browser click test | implement |
| 7 | Tool tiers that change mining speed | reference signature 4 | must | Visible improvement after crafting | Pickaxe multiplier applies per block class | `tests/mining.test.js` | implement |
| 8 | Day/night cycle with sky backdrop | reference signature 2 | must | The world feels alive; night matters | Phase advances; sky colours change; saved time restores | `tests/time.test.js` + day/night screenshots | implement |
| 9 | Skylight + torch light propagation | reference signature 3 | must | Caves are dark and lightable | Sky light falls underground; torch raises nearby light | `tests/lighting.test.js` + screenshot | implement |
| 10 | Torch item, craftable and placeable | reference signature 3 | must | The player can reclaim dark spaces | Torch recipe works; placed torch lights | `tests/crafting.test.js`, `tests/lighting.test.js` | implement |
| 11 | Save/load world, player, inventory, time, tasks, settings | user: "save progress" | must | Continuity across sessions | Round-trip equality; reload restores | `tests/save.test.js` + two-run browser persistence test | implement |
| 12 | Save fallback when storage is unavailable (export/import) | user: "save progress"; quality Q6 | must | Work is never silently lost | Storage error surfaces; export/import round-trips | `tests/save.test.js`; forced-failure browser check | implement |
| 13 | First-run affordance: welcome, visible buttons, task tracker | user: applied Q4 | must | Newcomer can start without a README | Welcome visible on first run; Play/Guide buttons work; tracker lists next task | browser selftest clicking DOM controls + screenshot | implement |
| 14 | Visual-state backdrop: before/after for edits, mode, time, viewport | user: applied Q5 | must | Changes stay reviewable, nothing vanishes silently | Edit records before/after; mode/time/zoom pulses visible; minimap trail | browser selftest + paired screenshots | implement |
| 15 | Experience lens applied (discoverability, visual review, progression) | user: applied Q8 | must | Design is judged on player experience | Goal/analysis/solution carry the lens; UI evidences it | document review + browser evidence | implement |
| 16 | Controls documented in-product and in README | user: "document the controls" | must | The player can learn every action | Guide lists all controls; README matches | static check of guide data + README read | implement |
| 17 | Task chain with rewards and visible progress | user: applied Q8; reference | must | A first session has a spine | Tasks complete on actions, reward once, persist | `tests/tasks.test.js` + browser selftest | implement |
| 18 | Minimap with viewport trail | user: applied Q5 (viewport) | should | Orientation; shows viewport before/after | Minimap renders; zoom leaves a previous-viewport outline | browser selftest + screenshot | implement |
| 19 | Procedural audio feedback (no asset files) | reference signature 1; offline constraint | should | Tactile feedback | Audio starts after gesture; mute persists | browser selftest (state), manual listen | implement |
| 20 | Zoom controls | user: applied Q5 (viewport); comfort | should | Readable view at any size | Wheel/keys change tile scale within bounds | `tests/camera.test.js` + screenshot pair | implement |
| 21 | Backdrop inspect mode | user: applied Q5 (mode) | should | Review recent edits at a glance | Mode toggles ghosts; mode pulse records before/after | browser selftest + screenshot pair | implement |
| 22 | Custom seed / new world | reference: seed worlds | should | Replayable worlds, save management | New seed regenerates and resets state | `tests/worldgen.test.js` + browser selftest | implement |
| 23 | Undo/redo of edits | reference; Q5 removed content | should | Mistakes are recoverable | Undo restores before-state; redo re-applies | `tests/backdrop.test.js` + browser selftest | implement |
| 24 | Ambient decorative critters | reference atmosphere | should | World feels inhabited | — | — | defer (impact: less life; re-entry: atmosphere pass) |
| 25 | Mobs, combat, health from damage | reference survival | should (proposed, user-silent) | Survival tension | — | — | defer (impact: no combat loop; reversible) |
| 26 | Hunger/food | reference survival | should (proposed, user-silent) | Survival pressure | — | — | defer (impact: no food loop; reversible) |
| 27 | Redstone/circuits | reference | should (proposed, user-silent) | Automation creativity | — | — | defer (impact: no automation; reversible) |
| 28 | Nether/dimensions | reference | should (proposed, user-silent) | Long-term exploration | — | — | defer (impact: one dimension only; reversible) |
| 29 | Furnace/workbench stations and 3×3 grid | reference crafting | should (proposed, user-silent) | Crafting ritual | — | — | defer (impact: recipe-list crafting is simpler; reversible) |
| 30 | Water/lava fluid simulation | reference | should (proposed, user-silent) | Environmental dynamics | — | — | defer (impact: static world; reversible) |
| 31 | Multiplayer | reference | non-goal | — | — | — | not applicable: user requires offline, no network |
| 32 | 3D voxel rendering | reference | non-goal | — | — | — | not applicable: user requires 2D |
| 33 | Touch/mobile controls | accessibility | should | Play on tablets | — | — | defer (impact: keyboard/mouse desktop assumed; re-entry: input abstraction) |

Rows 24–30 are reference-observed capabilities the request is silent about. They are recorded as
**proposed should** items deferred by the solution, never as excluded from the domain and never as
binding non-goals; the user can pull any of them back in. Rows 31–32 are non-goals because the user's
own wording ("2D", "offline... no network access") decides them.

## Signature-experience table

Reference: **Minecraft** (Java/Bedrock), credible because the product prompt names it and its
survival-sandbox loop is the shared target; evidence is the documented core loop (mining, building,
hotbar, crafting, day/night, light, seeds, saves). No empirical measurement of the reference was
performed here, so these decisions are reference-derived, not binding measurements.

| # | Signature experience | Evidence | Goal covers it? | Proposed decision | User value |
| --- | --- | --- | --- | --- | --- |
| S1 | Breaking/placing blocks is tactile (cracks, particles, sound, tool speed) | Reference mining loop | Yes (Q2) | must — depth requirement on rows 3, 4, 7, 19 | The core verb feels good |
| S2 | Living cyclic world (sky, sun/moon, day/night) | Reference day cycle | Yes (Q2, A5) | must — depth requirement on row 8 | Time pressure and atmosphere |
| S3 | Darkness needs light (skylight falloff, torches) | Reference lighting/caving | Yes (A5) | must — depth requirement on rows 9, 10 | Caves become explorable goals |
| S4 | Gathering converts into capability (wood → planks → sticks → tools) | Reference crafting/tools | Yes (A3) | must — depth requirement on rows 6, 7, 17 | Visible progression |
| S5 | A seed world is worth exploring (variety, caves, ore, trees) | Reference world generation | Yes (A4) | must — depth requirement on rows 2, 22 | Replayable exploration |
| S6 | Leaving and returning is safe (persistent save) | Reference save/worlds | Yes (Q6, A6) | must — depth requirement on rows 11, 12 | Trust in the world |

The six signature experiences all sharpen already-requested capabilities; none adds an unrequested
system. Rows 24–30 are the reference's *other* systems, and they are deferred rather than imported —
the reduced decision-changing set is used because the request is scoped by "small".

## Design options and trade-offs

| Decision | Options | Chosen | Why |
| --- | --- | --- | --- |
| D1 Code shape | single-file monolith; ES modules; UMD IIFE modules | UMD IIFE modules per concern | No build step, `file://` compatible, Node-testable like the seed, reviewable |
| D2 World rendering | DOM tile elements; canvas immediate; canvas + cached tile sprites | Canvas immediate draw with procedural tile detail | 60 fps over ~1k visible tiles, no asset files, precise pixel control for backdrop ghosts |
| D3 View | fixed 960×540; full viewport with adaptive canvas | Full viewport, DPR-aware backing store, zoom 0.6–2.5× | Feels like a game; supplies the real viewport-change axis for Q5 |
| D4 Save | localStorage; IndexedDB; files only | localStorage primary + auto/explicit save + JSON export/import + in-memory fallback | Probe confirms `file://` localStorage; export covers blocked storage |
| D5 Save payload | JSON array of tile ids; RLE base64; compressed | RLE over block ids + JSON envelope with version | ~22× smaller than an array while still human-inspectable and testable |
| D6 World size | 128×64 seed; 192×96; 256×128 | 192×96 (18,432 tiles) | Meaningful exploration without slow generation or heavy lighting |
| D7 Lighting | none; per-tile AO fake; flood-fill light levels | Flood-fill skylight + torch light, recomputed on edit/time | Reference signature S3; cost measured in browser |
| D8 Crafting | free-form 3×3 grid + stations; recipe list with unlocks | Recipe list with progressive unlocks and Craft buttons | Discoverability (Q4) and click-testability; grid/stations deferred (row 29) |
| D9 UI | all-canvas HUD; DOM overlay HUD | DOM overlay HUD over canvas world | Real buttons, focus, aria-live, and click-driven browser tests (Q4, Q7) |
| D10 Day length | 20 min (reference); 4 min; 1 min | 4 min full cycle (2 min daylight) | Night arrives in a first session without dragging |
| D11 First run | modal only; modal + persistent tracker + hints | Welcome modal with Play/Guide, persistent task tracker, contextual hints | Q4 requires visible affordance, not a key legend |
| D12 Backdrop | HUD before/after text only; world ghosts only; both + minimap trail | All three: edit ghosts, kind-labelled before/after pulse, minimap viewport trail | Q5 asks for removed/covered content *and* mode/time/viewport changes |
| D13 Verification | node tests only; node + page_check; + scripted browser selftest and screenshot pairs | All three layers | Logic, page shell, and real interaction/visual evidence |

## Hypotheses, unknowns and risks

- **Hypothesis (to measure):** flood-fill relighting of 18,432 tiles stays under ~8 ms so an edit can
  relight synchronously. If not, relight on a trailing timer without changing semantics.
- **Hypothesis:** a headless Chrome two-run test with a persistent `--user-data-dir` proves real save
  persistence across launches. Planned as the strongest save evidence; if Chrome resets `file://`
  storage between launches, record that and fall back to same-run reload evidence plus export/import.
- **Risk:** a full-screen first-run overlay must not hide the `#status` marker from `page_check.py`;
  the marker keeps the highest stacking context.
- **Risk:** `page_check.py`'s canvas colour sample must stay ≥12 buckets at first run (world must be
  visible behind the welcome overlay).
- **Unknown (resolved in verification):** exact rendering cost at 1600×1000 with lighting overlay.
- **No user gate requested:** no material human-owned decision is unresolved at analysis time; the
  applied Q4/Q5/Q8 requirements are explicit in the request, and the only narrowing is the deferred
  reference systems, recorded above with reversal paths.

## Request-to-goal comparison

The goal covers every user wording: playable 2D offline sandbox (A1–A3), Minecraft feel with the six
signature experiences (Q2, A4–A5), save progress (Q6, A6), documented controls (Q7, A9), plus the
applied requirements Q4, Q5, Q8. It narrows nothing: it adds no exclusion and explicitly refuses to
declare reference systems forbidden. Missing capabilities found: none material; the deferrals in rows
24–30 are proposed-should items and are carried to the solution, not silently dropped.
