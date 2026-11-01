---
schema_version: 1
document_kind: work-order-analysis
content_language: en
work_order_id: "20261030-1819-mc-2d-sandbox"
feature_ids: []
orchestration:
  main_tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Analysis: create scope, capability map and design evidence

## Evidence and current state

The seed at `project/` is a static shell, not an implementation:

- `index.html` provides ids `game`, `hud`, `hotbar`, `status`, four slots and five classic scripts;
  `#status` starts `data-state="booting"`.
- `css/style.css` supplies a dark 960x540 shell, a HUD box, a four-slot hotbar with `.is-selected`,
  and the yellow/green/red status marker.
- `js/config.js` fixes block ids (air/grass/dirt/stone/wood/leaves), tile 24, world 128x64, gravity,
  move speed, jump speed, reach 5 and `saveKey`.
- `js/world.js` builds a flat 128x64 world with the surface at `floor(height*0.65)=41` and offers
  bounded `getBlock`/`setBlock`, `isSolid` and JSON serialization.
- `js/player.js` is a placeholder: gravity and horizontal intent, no collision, no jump.
- `js/render.js` paints a sky gradient, flat blocks and a rectangle player; `js/main.js` renders once,
  then runs a static loop, sets `ready`, and exposes `window.__sandbox`.
- `tests/world.test.js` contains the six seed tests that pin the surface at x=10 (grass y=41, dirt y=42,
  stone y=63), air at (0,0), bounded block access, serialization and solidity. They must not change.
- `tools/page_check.py` checks required ids, local assets, no network references in the page and its
  references, the `ready` marker pixel and canvas colour variety, with `--screenshot` and
  `--window 960x600`.

Baseline commands before the change:

```console
node --test "tests/**/*.test.js"   # 6 seed tests pass
python tools/page_check.py         # static and headless runtime checks pass
```

The project bridge (`.xcoding/WORKFLOW.md`) fixes English/UTF-8/LF, no project commit, no build step,
`file://` operation, no third-party or network assets, Node-loadable modules, two-space JavaScript, the
`#status` marker contract and the two verification commands. `.xcoding/KNOWLEDGE.md` does not exist.
The L1 convention scan (node artifact of `prepare-work-order`) reported `not-applicable`: it enumerated
no project-owned C1/C2 file, and the bridge is the only declared convention source.

## Reconciliation

### Capability map

Sources: `request` = verbatim user request; `prior` = cumulative prior accepted inventory supplied by
the user; `project` = `.xcoding/WORKFLOW.md` and explicit user decisions; `reference` = the
block-sandbox genre evidence below. This table is canonical; the goal references it and the solution
carries it into the accepted capability matrix.

| # | Capability | Source | Priority | User value | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | Deterministic procedural terrain from a numeric seed with grass, dirt and stone | request | must | A seeded, authored-feeling world instead of a placeholder strip | Two worlds from one seed are identical, two seeds differ, layers are present, and the seed is visible/editable | determinism + layer unit tests; seeded page probe |
| C2 | Horizontal movement, gravity, jumping and tile collision that cannot be passed through | request | must | The sandbox is playable | Player moves, jumps, falls, lands and never overlaps a solid tile | physics unit tests; journey probe |
| C3 | Left-click mining of a block within reach | request | must | The genre's primary verb | A click within reach removes that block; out-of-reach/invalid clicks refuse with a reason | interaction unit tests; CDP click probe |
| C4 | Right-click placement in an empty adjacent cell, never over the player, with an explanation on refusal | request | must | Building is trustworthy and understandable | Valid placement places and consumes; occupied, player-overlap, unsupported, out-of-reach and empty-inventory attempts visibly refuse and leave the world unchanged | interaction unit tests; DOM toast probe |
| C5 | Hotbar with ≥4 block types, number-key selection and a visible selected state | request + prior | must | The palette is the player's inventory and mode indicator | Nine slots, keys 1–9, wheel cycling, exactly one selected ring, HUD names the block | UI unit tests; visual probe |
| C6 | Camera follows the player and stays inside the world bounds | request | must | The view stays legible and never shows void | Camera eases toward the player and clamps on both axes | camera unit tests; boundary probe |
| C7 | Save/load world and player state through localStorage, restored on page load | request | must | A sandbox that forgets is not a sandbox | Mine/place/move then reload restores world, position, counts and clock | persistence unit tests; real reload probe |
| C8 | Readable page with a controls hint, offline, `file://`, no external resources | request + project | must | Opens by double-click and stays self-contained | Hint visible; page check static clean; no network request | `page_check`; source inspection |
| C9 | README describes what was built, how to run it, controls and test commands | request | must | A reader can start and verify the page | README sections present and accurate | document review |
| C10 | `#status` marker contract preserved (`booting` → `ready`, red error) | project | must | Keeps the project's verification contract working | Marker reaches `ready`; an induced error turns it red | `page_check`; error-state probe |
| C11 | Automated tests, seed tests unchanged, covering terrain/collision/placement/persistence | request | must | Correctness evidence that survives future changes | `node --test` passes with ≥52 tests including the six seed tests | test run |
| C12 | No external libraries, CDNs, fonts or network requests | request + project | must | Portability and the sample's constraints | Page and its files contain no network reference | `page_check` |
| C13 | 960x600 screenshot inspected against the quality bar, plus an independent visual review | request (user) | must | The result is judged as an interface | Screenshot under `tmp/`; independent review artifact; required findings fixed and re-checked; M2D-SES v1.1 score | screenshot; `xc-review`; score sheet |
| C14 | Standard lifecycle stages recorded | request | must | The sample is a workflow reference | goal, analysis, solution, approval, implementation, verification and result artifacts exist | runtime + document validation |
| C15 | Per-block inventory counts | prior | must | Mining rewards the player and the palette shows progress | Mining adds a per-block count; placement consumes one; every slot shows its count | inventory tests; probe |
| C16 | 52 automated tests including the seed tests | prior | must | Regression depth | ≥52 tests pass | `node --test` count |
| C17 | Reduced-motion support | prior | should | Respects the OS preference | `prefers-reduced-motion` removes transitions and camera easing/particles | CSS check; matchMedia test |
| C18 | Wheel selection | prior | should | Fast palette switching | Wheel over the page cycles the selected slot | UI test; probe |
| C19 | 1280-wide scaling | prior | should | Intentional look on a desktop monitor | Layout grows to 1280 px keeping aspect ratio without overflow | CSS check; 1280x800 screenshot |
| C20 | Audio and mute | prior | should | Feedback without assets | Generated tones on mine/place/jump/select; one mute control, persisted | audio test; probe |
| C21 | Numeric seed entry | prior | should | Replayable worlds | Entering a seed regenerates and saves the world; invalid input refuses visibly | UI test; probe |
| C22 | Pause | prior | should | The player can stop the simulation | Pause freezes time and player and shows an overlay; resume restores | journey probe with two states |
| C23 | The eighth hotbar block | prior | should | Palette depth | At least eight distinct placeable block types | config/UI test |
| C24 | Day/night | prior | should | World atmosphere | Time advances; sky, lighting and clock change; foreground stays readable | time-cycle test; two screenshots |
| C25 | Nine-slot hotbar | prior | should | Palette breadth | Exactly nine slots with keys 1–9 | UI test; visual probe |
| C26 | Coordinates | prior | should | Orientation in the world | HUD shows live tile coordinates | UI test; probe |
| N1 | Multiplayer/network play | request (offline) | non-goal | — | — | — |
| N2 | Third-party libraries, CDN assets, external fonts | request + project | non-goal | — | — | — |
| N3 | Build step, bundler or server requirement | request + project | non-goal | — | — | — |
| N4 | Project Git commit | user (explicit) | non-goal | — | — | — |
| N5 | Change report | user (explicit waiver) | non-goal | — | — | — |

The map is a fidelity instrument, not a breadth target. C15–C26 are the prior accepted inventory and
are carried as continuity, not as an invitation to add unrelated features.

### Stateful journeys and integrity invariants

| # | Journey | Before → action → after (visible state) | Probe |
| --- | --- | --- | --- |
| J1 | Mine a surface block | Grass tile at the hovered cell, count 0 → left-click → the tile is replaced by the sky/background at the same spatial anchor, dust appears, toast `+1 grass`, badge shows 1 | CDP click; before/after screenshots; tile pixel becomes sky; badge increments |
| J2 | Place a block | Empty adjacent cell, selected block count ≥1 → right-click → the block is drawn in exactly that cell, count decreases, placement puff | CDP right-click; block pixel equals palette colour; badge decrements |
| J3 | Refused: occupied cell | Occupied cell → right-click → world visually unchanged, refusal toast names the reason | CDP right-click; block pixel unchanged; toast text |
| J4 | Refused: player overlap | Cell under the player → right-click → player sprite unchanged, refusal toast | CDP right-click; player pixel unchanged; toast text |
| J5 | Refused: no inventory | Selected leaves with count 0, valid empty cell → right-click → no block appears, toast `No leaves left — mine some first`, badge 0 | CDP right-click; cell stays background; toast text |
| J6 | Reload persistence | Mined/placed state, moved player, counts → reload → same layout, position and counts, `ready` marker, restore toast | CDP reload; read `window.__sandbox` snapshot; compare |
| J7 | Corrupt save recovery | `localStorage` replaced with `"{oops"` → reload → fresh world, `ready` marker, visible unreadable-save notice | CDP corrupt + reload; assert status and notice |
| J8 | Pause overlay | Running world, advancing clock → press `P` → canvas dimmed by an overlay with a centred `Paused` card, time/player frozen; press `P` → overlay gone, motion resumes | CDP key press; two screenshots; assert overlay visibility and dimmed canvas pixel |
| J9 | Day and night | Midday bright sky, strong contrast → advance the clock → deep-blue sky with stars/moon, darkened but readable world, night clock; day frame stays bright | CDP clock advance; two 960x600 screenshots; top-of-canvas pixels differ; foreground anchor visible in both |
| J10 | World boundary | Player near the world edge → walk outward → camera stops at the boundary, no out-of-world void, player stays inside | CDP held key; camera clamp values; edge pixel check |
| J11 | Hotbar selection | Slot 1 selected → press `5`, then wheel → exactly one selected ring at the correct slot, HUD name and coordinates agree, all counts visible | CDP key/wheel; class placement and HUD text |

Integrity invariants: I1 placement never overwrites solids or the player AABB; I2 the player never
intersects a solid tile after a step; I3 a save round-trip preserves seed, blocks, position, inventory
and clock or falls back with a visible notice (never a red error); I4 the camera rectangle never leaves
the world; I5 the selected index stays 0–8 and counts never go negative.

Visible-state obligation: J1 states the replacement background at the removed block's anchor;
J3–J5 state that the world stays visually unchanged while the refusal occupies the toast layer;
J8 names the occlusion layer and its dimming; J9 checks two materially different visual states with a
foreground anchor. All are executed probes at 960x600, not inspection-only claims.

### Signature-experience table

Reference: **Minecraft**, the genre's defining product; supporting evidence from browser-native 2D
block sandboxes for Canvas/`file://` delivery. The request itself names "Minecraft-style", so the
reference is credible and directly relevant; evidence is the reference's player-visible interaction
grammar.

| Signature capability | Evidence | Goal coverage | Decision |
| --- | --- | --- | --- |
| Immediate tactile break/build feedback | Blocks respond instantly with break animation, particles and sound | Covered in principle, must be explicit | must |
| Palette identity: small hotbar, per-block identity, selection and counts | Numbered hotbar with stack counts | Covered | must |
| Living atmosphere: day/night sky, light, sun/moon, parallax depth | Cycle changes mood without hiding the world | Prior day/night, not yet designed | must |
| Seed-driven world variety: layers, hills, trees, sand, caves | Seeded worlds yield landmarks and biomes | Requested terrain; variety is quality depth | must |
| "Return to your world" persistence with a visible restore cue | Worlds persist across sessions | Covered | must |
| Sound feedback with mute | Break/place sounds | Prior only | should |

Reduced set rationale: one compact sample page; six decision-changing rows instead of importing mobs,
crafting, redstone or multiplayer. A reference never removes a requested capability and is not a
feature-count target.

### Prior accepted capability dispositions

Source/version: initiating user instruction, cumulative inventory; no version tag supplied (uncertainty
recorded).

| Prior capability | Disposition | Reason / impact |
| --- | --- | --- |
| per-block inventory counts | improve | Mining adds, placement consumes, every slot shows a count; adds a resource model and empty-inventory refusal |
| 52 automated tests including the seed tests | improve | Keep all six seed tests; grow the suite to ≥52 over terrain, physics, interaction, persistence, time, camera, render, UI and journeys |
| reduced-motion support | preserve | `prefers-reduced-motion` disables transitions and JS camera easing/particles |
| wheel selection | preserve | Wheel cycles the nine slots |
| 1280-wide scaling | preserve | Layout scales to 1280 px with the canvas aspect ratio |
| audio/mute | preserve | WebAudio-generated tones with a persisted mute control |
| numeric seed entry | preserve | Seed field + generate action regenerates and saves a world |
| pause | preserve | `P`/button toggles a paused overlay and freezes simulation |
| the eighth hotbar block | preserve | Nine block types ship in the palette (at least eight placeable) |
| day/night | improve | A visible cycle drives sky, light and a clock badge |
| nine-slot hotbar | preserve | Exactly nine slots with keys 1–9 |
| coordinates | preserve | Live tile coordinates in the HUD |

No replace, retire or defer disposition is proposed; nothing is silently dropped.

### Goal-request comparison

- Every requested functional and acceptance bullet maps to C1–C14; no requested capability is missing
  from the goal.
- Goal-added constraints all have a `user` or `project` source; none is `goal-authored`.
- No unilateral narrowing: the goal's 52-test threshold and prior inventory raise ambition rather than
  remove requested work.
- Open decisions (resource model, variety depth, feedback set) are resolved in the alternatives below
  with recorded reasoning because no user is available; none becomes a silent exclusion.

## Impact and risks

- The six seed tests pin the surface at x=10, so terrain keeps a deliberate flat spawn plateau while
  varying elsewhere; this is a design constraint, not a test change.
- `file://` localStorage in Chrome works per file path but has origin quirks; the reload probe verifies
  it, and a corrupt/unavailable payload falls back to a fresh world with a visible notice.
- AudioContext requires a user gesture; audio initialises lazily on first input and fails silent.
- Headless capture depends on the first frame; `#status` reaches `ready` only after that frame.
- Pixel probes must read stable anchors with tolerance; clouds and particles must not cover the sampled
  anchors.
- `window.__sandbox` is a thin read/command surface for automated probes; it must not become a second
  control path for the UI.
- Scope risk: the accepted set is large for one page. Mitigation: two implementation units (simulation
  core; experience/presentation) with focused verification after each.

## Alternatives

1. **Terrain**: seeded value-noise heightmap over a flat spawn plateau with layer fill, trees, sand
   patches and carved caves (chosen) vs. cellular-automata caves on a flat surface vs. handcrafted maps.
   Chosen option is deterministic, seed-sensitive, survives the seed tests and produces visible variety
   in one pass.
2. **Collision**: axis-separated AABB resolution with sub-stepping at high fall speed (chosen) vs.
   per-pixel collision vs. an external physics library (forbidden).
3. **Resource model**: survival counts with a small starter kit, mining adds and placement consumes,
   explicit refusal reasons (chosen) vs. unlimited creative placement with counts as statistics vs. a
   crafting chain (out of scope). The chosen model preserves the prior inventory counts as a real
   mechanic and gives the required refusal explanation a second meaningful case.
4. **Persistence**: versioned JSON with run-length encoded blocks, a storage adapter and a corruption
   fallback (chosen) vs. raw arrays vs. IndexedDB. Chosen option is compact, inspectable, Node-testable
   and safe on `file://`.
5. **Rendering**: Canvas 2D with procedurally shaded tiles, sky/time, parallax and particles (chosen)
   vs. DOM tiles vs. WebGL. Chosen option needs no assets, fits `file://`, renders ~500 visible tiles
   comfortably and stays unit-testable with a recording context.
6. **Architecture**: keep the UMD module style and add focused modules — config, rng, world, player,
   inventory, interaction, persistence, timecycle, camera, render, ui model, audio, main — with pure
   logic importable in Node and DOM wiring only in `ui.js`/`main.js` (chosen) vs. one large script.

Recommendation: adopt the chosen option in each row, keep the accepted capability matrix in the
solution, and treat every must capability as blocking. No material ambiguity remains for solution
selection; the solution gate will record a self-approval decision because no user is available.
