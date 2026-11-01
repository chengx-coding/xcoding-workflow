---
schema_version: 1
document_kind: work-order-analysis
content_language: "en"
work_order_id: "20261101-2045-open-sandbox-xc-2"
feature_ids: []
orchestration:
  main_tree_ref: ".xcoding/work-orders/20261101-2045-open-sandbox-xc-2/runtime/orchestration.xml"
---

# Analysis — from a rendering seed to a small Minecraft

## Evidence and current state

The project is a 715-line plain HTML/CSS/JavaScript seed. It renders a flat 128x64 tile strip with a
static player rectangle, exposes `window.__sandbox`, and has no input, collision, interaction,
inventory, crafting, saving or help. Its six `node:test` cases pass and `tools/page_check.py` reports
`ok=true` with a green status pixel and 27 canvas colour buckets on the unchanged seed.

The seed's UMD module pattern lets Node tests require the same files the browser loads, and the page
check already proves the shell, local assets, no network references, a non-blank canvas and the status
indicator. The environment has Node v24.13.1 with a global `WebSocket`, Python 3.12.10, and Chrome for
real browser runs.

The seed tests are a live compatibility contract, not just examples: they require column 10 at
`floor(height * 0.65)` to be grass over dirt, require the bottom row to stay `stone`, require the JSON
serialization round-trip, and require air at `(0,0)`. The new generator must satisfy all of them
without editing the seed test file. The full evidence is in
`artifacts/analysis-seed/seed-and-constraints.md`.

`file://` persistence is the largest unproven assumption: the page check never writes storage. The
implementation must prove `localStorage` behaviour in a real browser and degrade safely if it is
unavailable.

## Reconciliation

`work_order.has_features=false` and `feature_ids=[]`; there are no feature baselines to reconcile and
no prior accepted capability inventory to disposition. This section is recorded as not applicable, not
silently skipped.

## Impact and risks

The change replaces the seed's placeholder world, player and renderer and adds new modules, tests,
browser evidence and documentation. Nothing outside the project is affected; there is no server,
network, data migration or public contract. The main risks are breadth (many interacting modules),
browser-only behaviour (storage, pointer mapping, audio), seed-test compatibility (column anchor and
bottom-row stone), performance of the light map, and scope creep from Minecraft's larger systems.

## Alternatives considered

| Decision | Chosen | Rejected alternatives | Reason |
| --- | --- | --- | --- |
| Rendering | Canvas 2D immediate mode | DOM tiles, WebGL | No library, simple pointer mapping, enough for ~40x23 tiles |
| World model | Row-major `Uint8Array` | Object map, chunk streaming | Seed-compatible, compact, fast; bounded world is enough |
| Terrain | Seeded noise heightmap + caves + ores + trees | Handcrafted map | Replayable new worlds, deterministic tests, exploration value |
| Physics | Fixed-step AABB, per-axis resolution | Per-frame Euler | Frame-rate independent and unit-testable |
| Lighting | Per-tile BFS from sky and torches | Global tint | Readable caves and meaningful torches at bounded cost |
| Crafting UI | DOM overlay | Canvas menus | Accessible, testable, simpler |
| Audio | Procedural WebAudio | Sample files, silence | No assets, small code, graceful fallback |
| Save | Versioned `localStorage` + RLE world | Cookies, IndexedDB | Synchronous, simple, adequate size |
| World size | 192x96 tiles at 24 px | Seed 128x64, larger | More exploration while one screenshot and one save stay manageable |

## Capability map (accepted)

| ID | Capability | Priority | User value | Verification |
| --- | --- | --- | --- | --- |
| C1 | `index.html` on `file://`, offline, no build step or external assets | must | The product is playable | Page check network/static scan; browser request log |
| C2 | 2D block world with generated terrain, caves, ores, trees | must | Exploration and materials | Generation unit tests; screenshots |
| C3 | Movement, gravity, collision, jump | must | Control of the character | Physics unit tests; real key events |
| C4 | Mining with reach, hardness, tool rules, feedback | must | The core verb | Rule unit tests; browser mining |
| C5 | Inventory, hotbar and selection | must | Carrying and choosing | Inventory unit tests; browser assertion |
| C6 | Placement from the hotbar | must | Building | Placement unit tests; browser placement |
| C7 | Save/restore world, inventory, player, time; safe recovery | must | Work survives | Save unit tests; real reload |
| C8 | Controls in README and in-game help | must | Players can learn | Content assertions; browser overlay |
| C9 | Crafting: planks, sticks, torches, wooden/stone pickaxe | should | Gathering has a goal | Crafting unit tests; browser craft |
| C10 | Day/night, darkness, torch light | should | Atmosphere and a use for coal | Light/time tests; day and night screenshots |
| C11 | Two-tier pickaxe gating | should | Progression and readable rules | Mining-rule unit tests |
| C12 | Procedural audio feedback and mute | should | Responsiveness | Browser audio-state check |
| C13 | Pause menu, new world, save status | should | Session control | Browser menu interactions |
| C14 | Blocky art, avatar animation, particles, HUD | should | Deliberate, not debug | Screenshot review |
| C15 | Responsive desktop layout | should | Playability at common sizes | Browser check at a second viewport |

The capability evidence and reference reasoning are in
`artifacts/analysis-product/product-signature.md`.

## Minecraft-system decisions (recorded)

The initiating instruction explicitly delegates crafting, survival, mobs, redstone and similar
system choices to this analysis. The decision is a **peaceful creative-survival hybrid** focused on
mining, building, exploring, crafting and light:

- **In:** block world, generated terrain and caves, ores, trees and static lakes, mining with tools,
  placeable blocks, inventory/hotbar, a small crafting tree (planks, sticks, torches, two pickaxes),
  day/night and torch light, procedural audio, particles and avatar animation, saving, help and a
  pause menu.
- **Out (recorded, with re-entry trigger):** health/hunger/death (S12), hostile mobs/combat (S13),
  redstone/mechanisms (S14), multiplayer (S15), 3D (S16), streaming/infinite worlds (S17), flowing
  liquids, farming, animals, villages and dimensions (S18).

These are decisions, not pre-declared requirements or prohibitions. Each non-goal names the user
value it would have to justify later and can be reopened by a user request or a failing acceptance
condition. The user-visible result is a Minecraft-like sandbox that is approachable in the first
minute rather than a survival game with a fail state.

## Scope assessment and recommendation

This is `create`, so there is no minimality presumption; the target is a small complete game rather
than a feature demo. The chosen scope is the accepted must matrix plus C9-C15, implemented as thin,
unit-testable modules with a fixed-step loop and a DOM UI layer. No version policy exists in the
project bridge, so no version change is proposed. The scope boundary is explicit: S12-S18 are out
unless a user request reopens them.

Recommendation: proceed to a solution that implements exactly this matrix and verifies it with the
seed suite, new unit tests, the page check, and a real interactive browser harness (DevTools Protocol,
real key/mouse events, reload persistence, screenshots). Deferred items: none from the must matrix;
all accepted should items are in the implementation scope.
