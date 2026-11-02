---
schema_version: 1
document_kind: work-order-analysis
content_language: "en"
work_order_id: "20261102-1550-open-sandbox-xc-047"
feature_ids: []
orchestration:
  main_tree_ref: ".xcoding/work-orders/20261102-1550-open-sandbox-xc-047/runtime/orchestration.xml"
---

# Analysis — how a small Minecraft-like 2D sandbox is made real here

## Context and evidence base

This is a `create` work order with no existing feature baseline and no prior accepted capability
inventory (`not applicable`). The evidence base is:

- the product request as recorded in `goal.md` (product prompt, verbatim scope);
- the project bridge `.xcoding/WORKFLOW.md` (constraints, verification commands, report waiver);
- the seed implementation in `index.html`, `css/style.css`, `js/*.js`, `tests/world.test.js` and
  `tools/page_check.py`, read in full;
- the L1 convention-discovery record
  (`artifacts/rt_work-order-20261102-1550-open-sandbox-xc-047__root__prepare-work-order/convention-discovery.md`);
- direct environment probes recorded below.

The one-shot workspace, the old compact sample and any evaluation material were not read; they are
not implementation inputs.

## Confirmed facts

| # | Fact | Evidence |
| --- | --- | --- |
| F1 | The seed is dependency-free classic browser JavaScript: UMD-style modules that also load under `require()` for `node --test`. | `js/config.js`, `js/world.js`, `js/player.js`, `js/render.js`, `js/main.js`; `tests/world.test.js` requires the modules directly. |
| F2 | `tools/page_check.py` enforces required element ids `game`, `status`, `hud`, `hotbar`, rejects every `http(s)://` or `//cdn` reference in page-served files, samples the canvas for ≥12 colour buckets, and requires the fixed status dot at viewport `(15, h-15)` to be within distance 70 of `rgb(46,204,113)` when ready. | `tools/page_check.py` lines 28–31, 151–175, 236–272. |
| F3 | The seed tests pin world-generation invariants: at `x=10`, `y=floor(height*0.65)` is grass, the next row is dirt, the bottom row is stone, `world.data.length == width*height`, and serialize/deserialize round-trips blocks and seed. | `tests/world.test.js` lines 17–51. |
| F4 | `file://` pages can use `localStorage` in the available Chrome: a probe page wrote, read and removed a value, round-tripped a 40,000-element byte vector through the same key, and reported `location.origin == "file://"`. | `tmp/file-storage-probe.html` run with `chrome --headless=new --dump-dom`; console output `write: ok | read: value-1 | 40k write/read: true | origin: file:// | protocol: file:`. |
| F5 | Classic `<script>` tags work from `file://`; ES module imports do not (CORS on `file://`). | File-system origin rules; the seed already uses classic scripts (F1). |
| F6 | Node.js v24.13.1 is installed and exposes a global `WebSocket`, and Chrome is installed, so a dependency-free DevTools-protocol harness can dispatch real browser input and capture evidence. | `node --version`; `node -e "typeof WebSocket"`; Chrome exists at `C:\Program Files\Google\Chrome\Application\chrome.exe`. |
| F7 | The seed page check already loads the page in headless Chrome and can keep a screenshot (`--screenshot <path>`), so visual evidence is available without new dependencies. | `tools/page_check.py` lines 178–195. |
| F8 | The seed world is a flat placeholder with no interaction; `js/player.js` and `js/main.js` comments explicitly leave collision, interaction, crafting, progression and saving to the implementation. | `js/player.js` lines 24–33; `js/main.js` line 51. |

## Reference analysis: what makes a sandbox feel like a small Minecraft

Reference: Minecraft (Mojang, 2011), the genre-defining block sandbox, and its 2D side-scrolling
descendants as the immediate visual/mechanical frame for a browser implementation. The reference is
used for domain legibility only; no Minecraft asset, name-bearing content or code is copied. These
are established, widely documented game mechanics, so the evidence is reference knowledge rather
than a byte-verified citation; each decision below is a design judgement for this product.

Signature elements and their disposition:

| Reference element | Why it is signature | Decision | User value / rationale |
| --- | --- | --- | --- |
| Block world with mining and placing | The verb of the genre: the world is made of editable cubes/tiles. | must | The primary interaction and the basis of building, the most Minecraft-like act. |
| Crafting as material conversion | Raw material is converted into capability; it turns collection into progression. | must | Without a conversion step the game is a gather demo. |
| Tool and material tiers that gate the world | Better tools unlock harder blocks and deeper resources; progression is legible and earned. | must | Gives the loop depth: wood → stone → iron → deeper goal, each tier required for the next. |
| Light and darkness | Caves are dark, torches make them usable, and light changes the mood of the world. | must | Creates the first real reason to craft and place something, and a strong visual state. |
| Day/night cycle | Time pressure and atmosphere; the world changes while the player prepares. | must | Provides pacing and a reason to build a shelter or light the base. |
| Survival pressure (health, hostile night presence) | Risk makes preparation matter and gives death/respawn meaning. | should | A light version: a small hostile night presence and contact damage, no hunger. Enough to make night matter without turning the game into a combat grind. |
| Progress saving and returning | A sandbox is a persistent world you come back to. | must | Explicitly requested ("save progress"); the world, inventory and progression must survive reload. |
| Large navigable world with orientation | Exploration needs a sense of place and direction. | must | The request asks for a sandbox world; a one-screen world would not read as one. A minimap, coordinates and depth give orientation. |
| A far goal that the world hints at | The reference's progression has a distant payoff. | should | A deep "Ember" material and a placeable beacon give the loop a destination and a win moment. It is a small, honest analogue of a boss/dimension goal, not a copy. |
| Sound feedback | Mining, placing and crafting want tactile response. | should | Procedural WebAudio effects add game feel with zero assets; no music dependency. |
| Hunger, farming, food | A survival sub-system. | non-goal | Adds inventory and time pressure but no new decisions at this scale; omitting keeps the small sandbox focused. Impact: no food loop; survival is health + night threat. |
| Tool durability | Wear and replacement. | non-goal | Adds grind and failure without a new kind of decision; the tier gate already drives tool progression. Impact: tools are permanent; progression stays about materials. |
| Water and lava fluid simulation | A physical system with propagation rules. | non-goal | Large implementation and rendering cost for a second-order benefit; caves are dry. Impact: no swimming or fluid hazards; emptiness reads as dry caverns. |
| Multiplayer, NPCs/villages, redstone, enchanting, dimensions, bosses | Breadth features. | non-goal | Outside a small single-player sandbox; each would dilute the core loop. Impact: single-player offline world with one surface and one deep layer. |
| Creative flight / instant build | A creative-mode convenience. | non-goal | The accepted loop is about earning capability; free flight removes the progression. Impact: the player builds with gathered blocks. |

The accepted `must`/`should` set is the signature challenge the goal asks for: the result must not
be a subset of the domain that stops at "mine a block".

## Design options

| Option | Shape | Assessment |
| --- | --- | --- |
| A. Side-view block sandbox with crafting, light, survival and a deep goal (chosen) | The seed's side view is kept; tiles, gravity, caves, tiers, torch light, night threat, minimap, save. | Best fit: the seed is already a side view with gravity and a camera; Minecraft's loop maps cleanly onto it; the reference signature set is expressible without a second technology. |
| B. Top-down builder | Free 2D movement, no gravity. | Would require discarding the seed's player/gravity/camera and loses the mining-into-depth fantasy that expresses "Minecraft" most directly. |
| C. Minimal gather-and-build demo | Movement, mining, placing, a few blocks. | Cheapest, but it is exactly the "thin gather-only demo" the goal rejects: no crafting depth, no tier gate, no reason to go deeper. |

Chosen: **Option A**. The scope is a small Minecraft, not a Minecraft clone: one surface world, one
underground depth, four material tiers, one hostile night presence, one world-scale goal.

## Capability map

Priority is `must` or `should`. Every `must` and `should` row has an implementation and verification
destination; `solution.md` carries the accepted matrix.

| # | Capability | Source | Priority | User value | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | Boot offline from `index.html` with no build, no external assets, no network | request | must | The only supported way to play. | Opening the file boots the game; page check finds no external reference. | `tools/page_check.py`; static review of served files. |
| C2 | First-run affordance and onboarding | request ("playable") + goal #2 | must | A new player knows how to start and what to do first. | Title overlay names the game, exposes one primary start control and the core controls; contextual hints appear after start. | Browser check: first-run visible, start via real pointer, overlay dismissed; screenshots. |
| C3 | Side-view movement and collision | request ("playable") | must | Basic playability and world traversal. | Run, jump, gravity, solid collision, coyote time, camera follow. | Unit tests for collision/physics; browser movement evidence. |
| C4 | Mining by real pointer hold with tool gating and drops | request ("sandbox", reference) + goal #5 | must | The defining interaction. | Hold pointer ≥90 ms on a reachable exposed block to break it; hardness and required tier respected; drop enters inventory. | Browser CDP pointer harness (10/10) + unit tests for gating/ hardness. |
| C5 | Block placement from the hotbar | reference | must | Building, the other half of the sandbox verb. | Right-click places the selected block into a valid empty adjacent tile and consumes one item. | Unit tests + browser placement evidence. |
| C6 | Inventory, hotbar and item counts | reference | must | Resources and tools must be usable and visible. | 36-slot inventory with 9-slot hotbar, stacking, click-to-move, wheel/number selection, HUD counts. | Unit tests for inventory; browser screenshot with counts. |
| C7 | Crafting with stations (hand, workbench, furnace) | reference | must | Converts gathering into capability; the core depth step. | Recipes matched by exact inputs, station proximity enforced, unavailable recipes explain why, output granted. | Unit tests for every recipe and station rule; browser craft evidence. |
| C8 | Tool tiers and ore gating | reference | must | Earned progression and a reason to descend. | Stone requires a wooden pickaxe; iron ore requires stone; ember ore requires iron; each tier speeds mining. | Unit tests for requirement/speed tables; browser progression evidence. |
| C9 | Procedural world: hills, forests, sand, caves, depth-banded ores | reference | must | A world worth exploring and a reason for tools. | Deterministic seeded generation; ≥2 caves, coal/iron/ember in depth bands; seed-test invariants preserved. | Unit tests for determinism, ore presence/bands, cave presence; minimap screenshot. |
| C10 | Light and darkness with placeable torches | reference | must | Makes caves playable and gives crafting a visible payoff. | Skylight by day; underground darkness; torch placement raises local light and is consumed. | Unit tests for the light function; screenshot comparison dark vs lit. |
| C11 | Day/night cycle and sky/backdrop state | reference + goal #6 | must | Pacing, atmosphere, visual state feedback. | Cycle advances, sky and light follow time, night is visibly different. | Unit tests for time math; day/night screenshots. |
| C12 | Survival: health, damage, respawn, night threat | reference | should | Makes preparing and lighting matter. | Contact damage with invulnerability window, health HUD, death and respawn at spawn, night-only spawns. | Unit tests for damage cooldown/death; browser state evidence. |
| C13 | Progression goal chain with persistent stage | reference + request | must | A destination and a legible sense of advancement. | 8-stage chain reaching the Ember Beacon; stages persist; HUD tracker and completion toasts. | Unit tests for stage transitions; save round-trip; browser evidence. |
| C14 | Save, load and continue with truthful save display | request | must | Progress survives closing the page. | Versioned localStorage save with RLE world; manual/auto save; Continue shows saved summary; reload restores world/inventory/progression. | Unit tests for codec/migration; browser reload evidence; screenshot. |
| C15 | Orientation: minimap, coordinates, depth, compass | goal #4 | must | A larger world stays navigable. | Always-visible minimap with player marker and surface profile, coordinates and depth readout. | Browser screenshot; unit tests for map sampling. |
| C16 | Visual art direction and state-responsive backdrop | goal #6 | must | The result reads as a game, not a debug canvas. | Procedural pixel textures, parallax sky, lighting, particles, HUD styled as part of the world. | Screenshots day/night/underground; visual inspection. |
| C17 | Procedural audio feedback | reference | should | Tactile response for mine/place/craft/hurt/quest. | WebAudio effects, muted toggle, no external audio files. | Browser muted/unmuted state; code review. |
| C18 | Controls documented in game and README | request | must | The request explicitly asks for it. | README documents every control; an in-game controls panel matches it. | Review of README and help panel; screenshot. |
| C19 | Test suite and browser interaction evidence | bridge + goal #9 | must | Proof that the game works. | `node --test` and `page_check.py` pass; CDP harness proves pointer, reload persistence and first-run flow. | The commands themselves; recorded artifacts. |

Non-goals (from the reference table): multiplayer, NPCs/villages, redstone, enchanting, dimensions,
bosses, hunger/farming, durability, fluid simulation, creative flight. None of these is required by
the request, and each would dilute the small-sandbox scope; their omission impact is recorded above.

No capability in the product prompt is missing from this map and no goal-authored narrowing exists.

## Loop and progression design

The loop, stated as the player experiences it:

1. **Arrive** in a meadow at dawn, with a minimap, a quest tracker and the three core controls.
2. **Gather** wood from trees by hand.
3. **Craft** planks → sticks → workbench (placed) → wooden pickaxe; the workbench must be placed,
   which introduces building as a mechanic.
4. **Dig** stone with the wooden pickaxe; craft stone tools at the workbench.
5. **Descend** for coal and iron; light the way with torches (stick + coal), which requires coal,
   which requires the stone pickaxe tier.
6. **Survive** the first night: hostile hollows appear in darkness away from light; health,
   respawn and light matter.
7. **Smelt** iron at a furnace (cobblestone + coal) into ingots; craft the iron pickaxe.
8. **Delve** below the iron band for Ember ore, which only an iron pickaxe can break.
9. **Raise the Ember Beacon** from ember shards, iron and stone bricks; placing it lights the deep
   and completes the goal chain, after which the sandbox continues.

Progression depth is therefore structural, not cosmetic: each tier is a prerequisite for the next
block type, the next station or the next depth band, and the goal needs three different refined
materials. The chain is 8 stages: gather wood, build a workbench, craft a wooden pickaxe, reach the
stone tier, light a torch, reach the iron tier, mine ember, raise the beacon.

## Technical design feasibility

- **Architecture** (all classic scripts, UMD for testability): `config` → `blocks` → `rng` → `world`
  (generation, RLE codec) → `player` (physics) → `inventory` → `crafting` (recipes, stations) →
  `progression` (stages) → `light` (skylight + torch BFS) → `mobs` → `save` → `render` (canvas,
  procedural textures) → `ui` (DOM overlays) → `input` (pointer/keyboard) → `audio` → `main`.
- **World size** 360×140 tiles at 24 px, with a flat spawn plateau that preserves the seed test's
  `x=10, y=ground` invariants and puts spawn at `x=24`.
- **Interaction model**: canvas pointer coordinates → camera → tile; press/hold mines the same
  target with accumulated progress; release cancels; right button places. Pointer capture prevents
  loss when leaving the canvas.
- **Lighting**: per-frame-visible light grid; sky contribution from the top-down column and a
  breadth-first torch propagation with a small radius. Computed on a dirty flag + time bucket, then
  composited as a smooth dark overlay, so torches genuinely light the cave and the day/night cycle
  changes the surface.
- **Save**: JSON envelope with schema version, seed, RLE-encoded block data, player, inventory,
  progression, clock and stats. localStorage under `file://` is proven to work (F4); failures are
  caught and surfaced as an in-game message rather than a crash. Corruption is rejected and the game
  offers a fresh world.
- **Browser interaction evidence**: a dependency-free Node script drives Chrome over the DevTools
  protocol (`Input.dispatchMouseEvent` is the same input path as a real mouse), holds the pointer at
  a computed tile for ≥90 ms, verifies the world changed and the state is consistent across ten
  trials, and also proves that a synthetic `element.click()` does not break blocks. It reloads the
  page to prove persistence, and captures screenshots. Node 24's global `WebSocket` (F6) makes this
  possible with no installed packages.
- **Rendering budget**: pre-rendered 24×24 tile variants, a 50×28 visible tile loop, one light overlay
  and a particle layer; comfortably 60 fps on the available hardware.

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Seed tests pin world invariants that a richer generator may break | Bridge violation if a seed test fails | Generate a flat plateau at `y=floor(height*0.65)` covering `x=10` and spawn at `x=24`; keep the bottom row stone. |
| `localStorage` unavailable or quota exceeded under `file://` | Save claim would be false | Probed working (F4); save wrapper catches quota/security errors and reports them; save payload is RLE-compressed (~5–20 KB). |
| Pointer evidence passes only because a synthetic click was used | Fails the interaction-truth requirement | The harness dispatches `Input.dispatchMouseEvent` press/release/hold, includes a negative control proving `element.click()` does not mine, and records trial-by-trial results. |
| Headless Chrome timing makes a 90 ms hold flaky | Unstable evidence | Hold 300 ms per trial (well over the threshold); break time for soft blocks is ~0.2 s by design; wait for explicit state predicates, not fixed sleeps. |
| First-run overlay blocks the pointer target | Interaction test or player frustration | Overlay is dismissed by a real pointer click on its primary button; the test waits for `data-state=playing` before mining. |
| Rendering too slow with lighting every frame | Jank | Cache the light grid; recompute on block change, time bucket or camera tile change only. |
| Canvas CSS scaling changes pointer→world mapping | Wrong tile targeted | Use one transform function from `getBoundingClientRect()` and test it with the same mapping the pointer test uses. |

## Unresolved decisions

None material. The product request is fully covered by the map above; the design decisions that the
prompt leaves open (which Minecraft systems to include) are recorded here with rationale and will be
accepted in `solution.md`. No human-owned decision is outstanding, and no `goal-authored` exclusion
needs confirmation because none was added.
