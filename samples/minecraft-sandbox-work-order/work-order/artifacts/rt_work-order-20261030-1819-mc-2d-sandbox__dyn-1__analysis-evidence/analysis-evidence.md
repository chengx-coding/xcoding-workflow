---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-1819-mc-2d-sandbox"
node_id: "rt_work-order-20261030-1819-mc-2d-sandbox__dyn-1__analysis-evidence"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Analysis evidence: create scope, capability map, signatures and design options

## Scope

`analysis_scope=solution-support` for the create work order. The node drafts the canonical capability
map, the stateful journey/integrity set, the reference signature table, the prior-capability
dispositions and the design options that `analysis.md` carries into the solution. It does not modify
product code, the goal, or the runtime tree beyond its own blackboard value.

## Evidence

### Confirmed current state (seed, read before any edit)

- `index.html` (982 bytes) has the required ids `game`, `hud`, `hotbar`, `status`; four `.slot` spans
  without counts; five classic scripts in dependency order; `#status` starts `data-state="booting"`.
- `css/style.css` (1.4 KB) is a dark shell: a 960x540 canvas, a HUD box, a four-slot hotbar with
  `.is-selected`, and the three status-marker colours (yellow/green/red).
- `js/config.js` has block ids air/grass/dirt/stone/wood/leaves, tile 24, world 128x64, gravity,
  speed, jump, reach 5, a save key, and six unit tests depend on these names.
- `js/world.js` generates a flat world (surface at `floor(height*0.65)=41`) with grass/dirt/stone,
  bounded `getBlock`/`setBlock`, solidity, and JSON serialization.
- `js/player.js` is explicitly a placeholder: gravity plus horizontal intent, no collision, no jump.
- `js/render.js` draws a sky gradient, flat coloured tiles and a rectangle player; no camera clamp is
  applied beyond `main.js`'s clamp helper, and `main.js` never updates the camera after boot.
- `js/main.js` boots, renders one frame and a static `requestAnimationFrame` loop, marks ready, and
  exposes `window.__sandbox = {world, player, camera, ready}`.
- `tests/world.test.js` holds six seed tests that must keep passing unchanged; they pin the surface at
  x=10 to grass at y=41, dirt at y=42, stone at y=63, air at (0,0), and a working round-trip.
- `tools/page_check.py` performs static checks (required ids, local assets exist, no network
  references in the page and its referenced files) and a headless-Chrome runtime check (status-marker
  pixel ≈ `rgb(46,204,113)`, canvas colour-bucket count ≥ 12), with `--screenshot` and
  `--window 960x600` options.
- `.xcoding/WORKFLOW.md` fixes: English, UTF-8+LF, no commit from this project, no build step, no
  third-party or network assets, `file://` operation, Node-loadable modules, two-space JavaScript,
  keep the `#status` marker, and the two verification commands.
- `.xcoding/KNOWLEDGE.md` does not exist; no knowledge source applies.
- L1 convention discovery: `not-applicable` (scan enumerated no C1/C2 candidate; the bridge is the
  only declared convention source), record under the prepare node's artifacts.

### Command evidence

```console
node --test "tests/**/*.test.js"      # seed baseline: 6 tests pass (skeleton behaviour)
python tools/page_check.py            # seed baseline: static + runtime checks pass
```

The skeleton is deliberately incomplete: no movement input, no collision, no mining/placement, no
camera follow during play, no persistence wiring, no day/night, no sound, no seed UI, no pause, no
counts, and no visual identity beyond flat rectangles. Every requested capability is therefore new
work, not a tweak.

## Findings

### Capability map (draft; `analysis.md` is canonical)

Sources: `request` = the verbatim user request; `prior` = the supplied prior accepted inventory;
`project` = `.xcoding/WORKFLOW.md`; `reference` = the block-sandbox genre evidence below.

| # | Capability | Source | Priority | User value | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | Deterministic procedural terrain from a numeric seed with grass, dirt, stone | request | must | The world feels authored and reproducible, not a flat placeholder | Same seed twice → byte-identical blocks; two seeds differ; layered surface; numeric seed shown and editable | unit determinism/layer tests + page probe |
| C2 | Player horizontal movement, gravity, jumping, tile collision that cannot be passed through | request | must | The sandbox is playable rather than a diorama | Move/jump/fall; player never overlaps a solid tile; landing sets grounded | physics unit tests + journey probe |
| C3 | Left-click mining of a block within reach | request | must | The core verb of the genre | Click within reach removes the block; outside reach/invalid target refuses with a reason | interaction unit tests + CDP click probe |
| C4 | Right-click placement in an empty adjacent cell, never over the player, with a refusal explanation | request | must | Building is the second core verb and must be trustworthy | Valid cell places and consumes; occupied/player-overlap/no-support/out-of-reach/empty-inventory refuse visibly and leave the world unchanged | interaction unit tests + DOM toast probe |
| C5 | Hotbar with ≥4 block types, number-key selection and visible selected state | request + prior | must | The palette is the player's inventory and mode indicator | 9 slots, keys 1–9, wheel cycles, one selected ring, HUD names the block | UI unit tests + visual probe |
| C6 | Camera follows the player and stays inside world bounds | request | must | The view stays legible and never shows void | Camera eases toward the player and clamps on both axes at every edge | camera unit tests + boundary probe |
| C7 | Save/load world and player state through localStorage, restored on page load | request | must | A sandbox that forgets is not a sandbox | Mine/place/move → reload → identical world, position and counts | journey probe with real reload |
| C8 | Readable page with a controls hint, offline, no external resources, `file://` | request + project | must | The page must open by double-click and stay self-contained | Hint line visible; `page_check` static check clean; no network request | `page_check` + source inspection |
| C9 | README describes what was built, how to run it, the controls and the test commands | request | must | A reader can start and verify the page | README sections present and accurate | document review |
| C10 | `#status` marker contract preserved (`booting` → `ready`, red error) | project | must | The project's verification contract keeps working | Marker reaches `ready`; an induced boot error turns it red | `page_check` + error-state probe |
| C11 | Automated tests, seed tests unchanged, coverage of terrain/collision/placement/persistence | request | must | Correctness evidence that survives future changes | `node --test` passes with ≥52 tests including the six seed tests | test run |
| C12 | Offline/no third-party assets at runtime | request + project | must | Portability and the sample's constraints | `page_check` static check clean; no network reference in shipped files | `page_check` |
| C13 | Rendered screenshot inspected and iterated against the quality bar, plus an independent visual review | request (user decisions) | must | The result is judged as an interface, not a diff | 960x600 screenshot captured under `tmp/`, inspected; independent review artifact with findings; required findings fixed and re-checked | screenshot + `xc-review` + M2D-SES v1.1 score |
| C14 | Standard lifecycle stages recorded | request | must | The sample is a workflow reference | goal, analysis, solution, approval, implementation, verification and result artifacts exist | runtime + document validation |
| C15 | Per-block inventory counts | prior | should→must via quality bar | Mining rewards the player and the palette shows progress | Counts increase on mining and decrease on placement, shown per slot | inventory unit tests + probe |
| C16 | 52 automated tests including the seed tests | prior | should | Regression depth | ≥52 tests pass | test run count |
| C17 | Reduced-motion support | prior | should | Respects the user's OS preference | `prefers-reduced-motion` disables transitions and camera easing/particles | CSS/source check + matchMedia unit test |
| C18 | Wheel selection | prior | should | Fast palette switching | Wheel over the canvas cycles the selected slot | UI unit test + probe |
| C19 | 1280-wide scaling | prior | should | Looks intentional on a desktop monitor | Layout grows to 1280 px and keeps aspect ratio, no overflow | CSS check + 1280x800 screenshot |
| C20 | Audio/mute | prior | should | Feedback without assets | Generated tones on mine/place/jump/select; one mute control persists | audio unit test + probe |
| C21 | Numeric seed entry | prior | should | Replayable worlds | Entering a seed regenerates and saves a world; invalid input is refused visibly | UI unit test + probe |
| C22 | Pause | prior | should | Lets the player stop the simulation | Pause freezes time/player and shows an overlay; resume restores | journey probe with two states |
| C23 | The eighth hotbar block | prior | should | Palette depth | At least eight distinct placeable block types | config/UI test |
| C24 | Day/night | prior | should | World atmosphere | Time advances, sky/lighting and clock change, foreground stays readable | time-cycle test + two screenshots |
| C25 | Nine-slot hotbar | prior | should | Palette breadth | Exactly nine slots, keys 1–9 | UI test + visual probe |
| C26 | Coordinates | prior | should | Orientation in the world | HUD shows live tile coordinates | UI test + probe |
| N1 | Multiplayer, network play | request (offline) | non-goal | — | — | — |
| N2 | Third-party libraries, CDN assets, external fonts | request + project | non-goal | — | — | — |
| N3 | Build step, bundler, server requirement | request + project | non-goal | — | — | — |
| N4 | Project Git commit | user (explicit) | non-goal | — | — | — |
| N5 | Change report | user (explicit waiver) | non-goal | — | — | — |

Priority note: C15–C26 are the prior accepted inventory. They are not a second feature list; the ones
above are either required for the quality bar or cheap continuity that the same implementation unit
already carries. Two items (C19, C17) are quality/accessibility continuity rather than new product
surface.

### Stateful journeys and integrity invariants (visible state)

| # | Journey | Before | Action | After (visible state) | Verification probe |
| --- | --- | --- | --- | --- | --- |
| J1 | Mine a surface block | Grass tile drawn at the hovered cell, count 0 | Left-click the cell | The tile is gone and the sky/background shows through that exact cell, a dust burst appears and the toast reads `+1 grass`; count becomes 1 | CDP click at a surface tile; screenshot before/after; assert the tile pixel becomes sky-coloured and the slot badge increments |
| J2 | Place into a valid cell | Adjacent empty cell, selected block with count ≥1 | Right-click the cell | New block is drawn exactly in that cell, count drops by 1, small placement puff | CDP right-click; assert block pixel equals the block's palette colour and badge decrements |
| J3 | Refused placement (occupied cell) | Occupied cell under the pointer, some selected count | Right-click the cell | World is unchanged; a visible refusal toast names the reason; canvas still shows the original block | CDP right-click; assert block pixel unchanged and the toast element is visible with the reason text |
| J4 | Refused placement (player overlap) | Cell overlapping the player's body | Right-click that cell | Player sprite unchanged; refusal toast `You are standing there` | CDP right-click on the player cell; assert player pixel unchanged and toast text |
| J5 | Refused placement (no inventory) | Selected leaves block with count 0 | Right-click a valid empty cell | No block appears; toast `No leaves left — mine some first`; slot badge shows 0 | CDP right-click; assert empty cell stays background and toast text |
| J6 | Reload persistence | Mined/placed state, moved player, counts | Reload the page | Same block layout, same player position and counts, status ready, restore toast | CDP `Page.reload`, read `window.__sandbox` snapshot and screenshot; assert values equal pre-reload |
| J7 | Corrupt save recovery | `localStorage` payload replaced with `"{oops"` | Reload the page | A fresh deterministic world renders, status ready, and a visible notice says the save was unreadable; no red error state | CDP write corrupt payload, reload, assert status ready + notice text + a fresh world sample |
| J8 | Pause overlay | Running world, clock advancing | Press `P` | Canvas is dimmed by a translucent overlay with a centred `Paused` card; time and player freeze; press `P` again → overlay gone and motion resumes | CDP key press, two screenshots, assert overlay element visible and dimmed pixel over canvas, then hidden |
| J9 | Day and night | Clock at midday, bright sky, strong contrast | Advance time to night (or set the clock) | Sky becomes deep blue with stars/moon, world is darkened but still readable, HUD clock reads night; day screenshot remains bright | CDP set clock; two screenshots at 960x600; assert top-of-canvas pixel differs between states and a foreground block stays visible in both |
| J10 | World boundary | Player near the world edge | Walk outward | Camera stops at the boundary; no out-of-world void is shown; the player stays inside | CDP hold movement key; assert camera clamp values and no void pixel column |
| J11 | Hotbar selection | Slot 1 selected | Press `5`, then wheel | Exactly one slot carries the selected ring at the correct spatial anchor; HUD block name and coordinates agree; counts visible on every slot | CDP key/wheel; assert class placement and HUD text |

Integrity invariants that must hold across the journeys:

- I1: a placement never overwrites a solid block or the player's AABB.
- I2: after any physics step the player's AABB does not intersect a solid tile.
- I3: a save round-trip preserves seed, world blocks, player position, inventory and clock, or the page
  falls back safely with a visible notice (never a red error screen).
- I4: the camera rectangle never leaves the world rectangle.
- I5: the selected index stays 0–8 and inventory counts never become negative.

Visible-state obligations are explicit: J1 states that the removed block is replaced by the
background/sky at the same spatial anchor; J3/J4/J5 state that the world is visually unchanged while
the refusal occupies the toast layer; J8 states the occlusion layer and its dimming; J9 states two
materially different visual states (day and night) including a spatial anchor that stays readable. The
video states are checked with executed probes at 960x600, not by inspection alone.

### Signature-experience table

Reference: **Minecraft** (the block-sandbox genre's defining product), with browser-native 2D block
sandboxes as supporting evidence for the `file://`/Canvas delivery. Why credible: the request names
"Minecraft-style", and the genre's interaction grammar (palette, instant break/place, seed worlds,
day/night, persistence) is directly observable in the reference product and its documented behaviour.
Evidence is the reference's well-known player-visible surface, not an internal design document.

| Signature capability | Evidence in the reference | Current goal | Decision (user value) |
| --- | --- | --- | --- |
| Immediate tactile break/build feedback | Blocks respond at once with a break animation, particles and sound | Covered in principle; must be made explicit | **must** — without instant, legible feedback the page feels like a static editor |
| Palette identity: a small hotbar with per-block identity, selection and counts | Hotbar with numbered slots and stack counts | Covered (hotbar, selected state, counts from prior) | **must** — the palette is how the player understands the world |
| Living atmosphere: day/night sky, light, sun/moon, parallax depth | The reference's day/night cycle changes colour and mood without hiding the world | Covered (day/night prior) but not yet designed | **must** — atmosphere is what separates a sandbox from a tile demo |
| Seed-driven world variety: layered terrain plus hills, trees, sand, caves | Seeded worlds produce recognisable biomes and landmarks | Covered (procedural terrain requested); variety is the quality depth | **must** — variety is named in the quality contract |
| "Return to your world" persistence with a visible restore cue | Worlds persist between sessions | Covered (localStorage requested) | **must** — persistence plus feedback is the trust contract |
| Sound feedback with mute | Break/place/step sounds | Prior inventory only | **should** — cheap, high-perceived-quality, and already accepted |

Reduced set rationale: the task is a compact sample with one page and one lifecycle run, so the table
keeps six decision-changing rows instead of importing the reference's mobs, crafting, redstone or
multiplayer. Importing those would be over-scope; omitting the six would make the result feel like a
subset of the genre.

### Prior accepted capability dispositions

Source/version: initiating user instruction, cumulative inventory; no version tag supplied (recorded as
uncertain). Canonical table lives in `analysis.md`; this node records the proposed disposition.

| Prior capability | Disposition | Reason / impact |
| --- | --- | --- |
| per-block inventory counts | improve | Mining adds a per-block count, placement consumes it and every slot shows its count; impact: a resource model exists, with refusal toasts when empty |
| 52 automated tests including the seed tests | improve | Keep the six seed tests unchanged and grow the suite to ≥52 across terrain, physics, interaction, persistence, time, camera, render, UI and journeys |
| reduced-motion support | preserve | `prefers-reduced-motion` disables CSS transitions and JS camera easing/particles |
| wheel selection | preserve | Wheel cycles the nine slots |
| 1280-wide scaling | preserve | Layout scales to 1280 px while the canvas keeps its aspect ratio |
| audio/mute | preserve | WebAudio-generated tones with a persisted mute control |
| numeric seed entry | preserve | Seed field + generate action regenerates and saves the world |
| pause | preserve | `P`/button toggles a paused overlay and freezes simulation |
| the eighth hotbar block | preserve | Nine block types (at least eight placeable) ship in the palette |
| day/night | improve | A visible time-of-day cycle drives sky, light and the clock badge |
| nine-slot hotbar | preserve | Exactly nine slots with keys 1–9 |
| coordinates | preserve | Live tile coordinates in the HUD |

No `replace`, `retire` or `defer` is proposed, so no unsourced removal or deferral exists.

### Goal-request comparison

- Requested outcomes: all eight functional bullets and every acceptance bullet map to C1–C14.
- Missing capabilities: none. The goal does not omit a requested capability.
- Goal-added constraints: offline/no-network, `file://`, marker/layout preservation, Node-loadable
  modules and seed-test preservation all come from the request or the bridge; no commit, report waiver,
  no-user-gate and isolation come from explicit user decisions. No `goal-authored` exclusion exists.
- Narrowing: none found. The goal's 52-test threshold comes from the prior inventory and raises rather
  than lowers the request.
- Open decisions (carried, not excluded): resource model, variety depth and feedback set; resolutions
  proposed below with reasoning because no user is available.

### Design options and trade-offs

1. **Terrain**: (A) seeded value-noise heightmap over a flat spawn plateau, layer fill, trees, sand
   patches and carved caves; (B) cellular-automata caves over a flat surface; (C) handcrafted maps.
   Choose A: deterministic, seed-sensitive, satisfies the seed tests through a documented spawn
   plateau, and yields visible variety with one pass.
2. **Physics/collision**: (A) axis-separated AABB resolution against solid tiles with sub-stepping at
   high fall speed; (B) per-pixel collision; (C) a physics library (forbidden). Choose A: standard,
   testable, no dependency, no tunneling.
3. **Interaction/resource model**: (A) survival counts with a small starter kit, mining adds and
   placement consumes, explicit refusal reasons; (B) unlimited creative placement with counts as
   statistics; (C) crafting chain. Choose A: preserves the prior inventory counts as a real mechanic,
   gives the required refusal explanation a meaningful second case, and the starter kit keeps every
   slot immediately usable without a crafting UI.
4. **Persistence**: (A) versioned JSON payload with run-length encoded blocks, a storage adapter and a
   corruption fallback; (B) raw block arrays (large), (C) IndexedDB (overkill). Choose A: small,
   inspectable, testable in Node with an in-memory adapter, and safe on `file://`.
5. **Rendering**: (A) Canvas 2D with procedurally shaded tiles, sky/time system, parallax, particles
   and a night light; (B) DOM tiles; (C) WebGL. Choose A: no assets, fits `file://`, fast enough for
   ~500 visible tiles, and keeps the renderer testable with a recording context.
6. **UI/architecture**: (A) keep the UMD module style and add focused modules (config, rng, world,
   player, inventory, interaction, persistence, timecycle, camera, render, ui-model, audio, main), with
   pure logic importable in Node and DOM wiring only in `ui.js`/`main.js`; (B) one large script.
   Choose A: the seed tests and Node-loadability require it, and it keeps unit tests honest.

### Risks and unknowns

- The six seed tests pin the surface at x=10, so terrain must keep a deliberate flat spawn plateau
  (x≈0–24) while varying elsewhere. Confirmed compatible by design.
- `file://` localStorage behaviour in Chrome: allowed per file path, but origin semantics differ from
  http(s). Must be verified by the reload probe, with an in-memory fallback that still renders.
- AudioContext requires a user gesture; audio must lazy-initialise on first input and fail silent.
- Headless screenshot timing: `requestAnimationFrame` must have produced a frame before capture; the
  page sets `ready` after the first frame, and `page_check` waits with a virtual-time budget.
- Screenshot pixel probes can be brittle if the scene animates (clouds/particles); probes should read
  stable anchors (top-centre sky, a chosen tile centre) and allow small colour tolerance.
- The `window.__sandbox` debug surface used by probes must stay a thin read/command layer and must not
  become a second control path for the UI.
- Scope risk: the accepted capability set is large for one page. Mitigation: two implementation units
  (simulation core, then experience/presentation) with focused verification after each, and no
  capability beyond the matrix.

## Conclusion

The seed is a shell, the request is fully covered by C1–C14, and the prior inventory is fully
dispositioned with no removals. Analysis recommends the option set above and hands the canonical map,
journey/integrity set and signature decisions to `analysis.md`, then to the solution matrix. No
material ambiguity blocks solution selection; the three open decisions are resolved by recorded design
reasoning, with the resource model resolved as survival counts plus a starter kit so that placement
refusal is both meaningful and visibly explained.
