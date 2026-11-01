---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261101-2045-open-sandbox-xc-2"
node_id: "rt_work-order-20261101-2045-open-sandbox-xc-2__dyn-1__product-signature"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261101-2045-open-sandbox-xc-2/runtime/orchestration.xml"
---

# Minecraft reference, capability map and design options

## Reference and evidence

**Minecraft (Java/Bedrock)** is the requested inspiration and the primary reference. Its
signature loop is: a world made of blocks -> explore generated terrain -> break blocks with the right
tool -> collect drops -> craft and place -> build something -> the world persists. The 2D translation
adds a second credible reference, **Terraria**, for how a side-view tile world presents movement,
mining, placing, hotbar selection and inventory. Both references are used to challenge signature
depth, not to import features the request does not support.

## Signature-experience table

| # | Signature experience | Why it defines the reference | Goal coverage | Decision and user value |
| --- | --- | --- | --- | --- |
| S1 | World made of mineable and placeable blocks | The irreducible Minecraft verb pair | Covered by requested outcome | **must** — without it the product is not Minecraft-like |
| S2 | Generated, explorable terrain with surface and underground | Exploration is why the block world is interesting | Covered by quality contract 2 and 3 | **must** — gives play direction and discovery |
| S3 | Reach-limited break/place with visible feedback | Interaction grammar players expect | Covered by quality contract 2 | **must** — turns tiles into a game action |
| S4 | Carried inventory and hotbar selection | The player's interface to the world | Covered by quality contract 2 and 4 | **must** — required to build anything meaningful |
| S5 | Progress survives leaving and returning | Explicitly requested ("save progress") | Covered by acceptance 5 | **must** — a sandbox without persistence loses the player's work |
| S6 | Crafting progression that turns raw blocks into useful items | Minecraft's early-game purpose loop | Not explicit in the prompt; reference-observed | **should, accepted** — a small recipe tree gives mining a goal and makes coal worth finding |
| S7 | Day/night rhythm with darkness and light sources | Minecraft's strongest atmospheric signature | Not explicit; reference-observed | **should, accepted** — cheap to implement, makes torches and coal meaningful, gives sessions a rhythm |
| S8 | Tool tiers that gate what can be mined | Wood -> stone progression is the first Minecraft lesson | Not explicit; reference-observed | **should, accepted** — a compact two-tier tree adds purpose without a durability system |
| S9 | Audio feedback for digging, placing, jumping, crafting | Silence reads as a prototype | Not explicit; reference-observed | **should, accepted** — procedural WebAudio, zero assets, large perceived-quality gain |
| S10 | Pause menu, new world, explicit save | Expected sandbox shell | Implied by playability and saving | **should, accepted** — makes persistence controllable and recoverable |
| S11 | Particles, block-break cracks, animated blocky avatar | "Feels like a game" rather than a debug canvas | Implied by "playable" | **should, accepted** — low-risk polish with high felt quality |
| S12 | Health, hunger, fall damage, death and respawn | Minecraft survival mode | Not requested | **non-goal, decision** — adds fail states, tuning and recovery UI that crowd out the requested mining/building/exploration loop; the small product is a peaceful creative-survival hybrid |
| S13 | Hostile mobs and combat | A major Minecraft system | Not requested | **non-goal, decision** — AI, spawning, combat, balancing and asset work form a second game; no request source requires it |
| S14 | Redstone or other mechanism systems | Advanced Minecraft system | Not requested | **non-goal, decision** — far outside "small"; no user value at this scale |
| S15 | Multiplayer or any network feature | Minecraft has multiplayer | Contradicted by "offline ... no network access" | **non-goal, constraint** |
| S16 | 3D or voxel rendering | Minecraft is 3D | Contradicted by "2D" | **non-goal, constraint** |
| S17 | Infinite or streamed world | Large Minecraft worlds | Not requested | **non-goal, decision** — a bounded 192x96 world is explorable and keeps save/lighting/render costs predictable |
| S18 | Flowing liquids, farming, animals, villages, dimensions | Later Minecraft systems | Not requested | **non-goal, decision** — each is a separate simulation; static lakes provide the visual without the update-order complexity |

The S12-S18 decisions are **analysis decisions made under the initiating instruction**, which
explicitly delegates Minecraft-system selection to this work order ("let analysis decide and record
the choice"). They are not pre-declared requirements or prohibitions, and each carries a re-entry
trigger: a user request or a failing acceptance condition can reopen it through a new work order.

## Capability map

Source column: `user` = the product prompt or the initiating delegation; `reference` = signature
evidence from Minecraft/Terraria used to sharpen an already-requested capability.

| ID | Capability | Source | Priority | User value | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | Opens from `index.html` on `file://`, offline, no build step, no external libraries/CDNs/network | user | must | The product is playable at all | Page boots with no network request and no console error | `page_check.py` static/network scan; browser check with request logging |
| C2 | 2D block world with generated terrain, caves, ores and trees | user | must | Exploration and material variety | A seeded world has surface, underground, caves and resources; more than a flat strip | Unit tests on generation invariants + browser screenshot |
| C3 | Player movement, gravity, collision and jump | user | must | Basic control of the character | Keys move/jump; the player stands on and cannot pass through solid blocks | Physics unit tests + real key events in the browser check |
| C4 | Mining with reach, block hardness, tool rules and feedback | user | must | The core Minecraft verb | Holding the primary button breaks a reachable block after its break time; invalid targets refuse with feedback | Unit tests for reach/hardness/drops + browser mining test |
| C5 | Inventory, hotbar and selection | user | must | Carrying and choosing what to build with | Broken blocks enter the inventory; 1-9 and wheel select slots; counts render | Inventory unit tests + browser hotbar assertion |
| C6 | Block placement from the hotbar | user | must | Building | Secondary click places the selected block in a reachable empty tile and decrements the count | Placement unit tests + browser placement test |
| C7 | Save and restore world, inventory, player and time; safe recovery | user | must | The player's work survives | Reload restores edits, inventory and position; corrupt save starts a fresh playable world with a message | Save round-trip/corruption unit tests + real reload in the browser check |
| C8 | Controls documented in README and discoverable in-game | user | must | Players can learn the game | README has a controls table; the game has a help overlay listing the same controls | Static content assertions + browser overlay test |
| C9 | Crafting progression (planks, sticks, torches, wooden/stone pickaxe) | reference | should | Turns gathering into a goal | Recipes consume and produce the documented amounts and are reachable from gathered materials | Crafting unit tests + browser craft test |
| C10 | Day/night cycle, darkness, torch light | reference | should | Atmosphere and a use for coal | Time advances; sky/light change; torches light their surroundings and the dark hides distant caves | Light/time unit tests + screenshots at day and night |
| C11 | Two-tier pickaxe gating | reference | should | Progression and readable rules | Stone/ore require a pickaxe; stone pickaxe is craftable and does not change hand-mineable blocks | Mining-rule unit tests |
| C12 | Procedural audio feedback | reference | should | The game feels responsive | First gesture enables audio; actions produce short synthesized sounds; mute works | Browser audio state/action check (no external asset) |
| C13 | Pause menu, new world, save status | user | should | Control over the session | Escape pauses; save, resume and new-world work; a save indicator appears after autosave | Browser menu interactions |
| C14 | Readable presentation: blocky art, avatar animation, particles, HUD | user | should | The result looks deliberate | Blocks are visually distinguishable; the avatar animates; break/place feedback is visible | Screenshot review + browser assertions |
| C15 | Responsive layout for common desktop sizes | user | should | Playability on a normal browser window | Canvas scales without breaking pointer mapping | Browser check at a second viewport size |

Every `must` capability maps to at least one verification instrument. No capability has an
`analysis`-only source: the analysis decisions above derive from the user prompt, the user's explicit
delegation of Minecraft-system selection, or reference evidence used to sharpen an existing request.

## Request-to-goal comparison

The goal covers every capability the prompt requires (C1-C8) and adds no new product requirement. It
does not narrow the request: the four prompt sentences map to C1 (offline run), C2-C6 (playable 2D
Minecraft sandbox), C7 (save progress) and C8 (document controls). The signature-derived C9-C15 are
sharpeners of "playable" and "feel like a small Minecraft", each with a user-value statement; C9-C12
are accepted `should` items and C13-C15 support the required experience.

## Technical design alternatives

| Decision | Alternatives | Choice and reason |
| --- | --- | --- |
| Renderer | DOM tiles, Canvas 2D, WebGL | **Canvas 2D immediate mode** — no library, straightforward pointer mapping, procedural pixel art, 40x23 visible tiles is cheap |
| World storage | Object map, row-major `Uint8Array` | **Row-major `Uint8Array`** — seed-compatible, compact, fast indexing, easy RLE save |
| Terrain | Handcrafted map, noise heightmap + structures | **Seeded value-noise heightmap with amplitude ramp, 2D cave noise, ore veins, trees** — replayable "new world", deterministic tests, seed-test column anchor satisfied by the ramp |
| Physics | Per-frame Euler, fixed-step AABB | **Fixed-step AABB with per-axis resolution** — frame-rate independent, unit-testable, no tunnelling at normal speeds |
| Lighting | Global tint only, per-tile BFS light | **Per-tile BFS over sky-exposed air and torches**, recomputed on edits and quantized time buckets — readable caves and torches, bounded cost |
| Crafting UI | Canvas-drawn, DOM overlay | **DOM overlay with recipe buttons** — accessible, testable, no canvas hit-testing for menus |
| Audio | None, sampled assets, WebAudio synthesis | **WebAudio oscillators/noise** — no external files, tiny code, graceful if unavailable |
| Persistence | Cookies, IndexedDB, `localStorage` | **Versioned `localStorage` snapshot with RLE world** — synchronous, simple, adequate size; try/catch and memory fallback |
| World size | 128x64 seed, 192x96, larger | **192x96 tiles at 24 px** — more exploration, still one screen-friendly save; seed assertions hold |
| Starting inventory | None, starter kit | **Empty inventory with guided toasts** — the first tree punch is the Minecraft opening; goals stay meaningful |

## Scope assessment (create)

`create` has no minimality presumption. The chosen scope is a **small complete game**, not a demo:
roughly ten focused JavaScript modules plus tests, browser harness and documentation. The release
trigger is the accepted solution plus passing verification; there is no version-number policy in the
bridge, so no version change is proposed. The scope is deliberately bounded by S12-S18; any widening
(combat, survival, mechanisms, streaming) is a new work order with its own solution and approval.

## Risks

- **Implementation breadth.** A game has many interacting parts. Mitigation: thin modules with
  explicit contracts, unit tests for logic, and a fixed-step loop.
- **Browser-only behaviour.** Persistence, pointer mapping and audio cannot be proven by Node tests.
  Mitigation: the DevTools-Protocol harness drives real input and reloads the real page.
- **Seed-test compatibility.** The world generator must respect the column-10 anchor and bottom-row
  stone. Mitigation: the amplitude ramp starts at zero and the floor is unbreakable by rule.
- **Scope creep from reference features.** Mitigation: the recorded non-goals and their re-entry
  trigger; the solution must implement only the accepted matrix.
- **Performance.** Full light recomputation and terrain drawing could jank. Mitigation: visible-tile
  culling, quantized light recomputation, and browser frame-time sampling.
