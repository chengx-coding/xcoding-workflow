---
schema_version: 1
document_kind: work-order-goal
content_language: en
work_order_id: 20261104-1337-2d-sandbox-game
feature_ids: []
orchestration:
  main_tree_ref: /work/.xcoding/work-orders/20261104-1337-2d-sandbox-game/runtime/orchestration.xml
---

# Work Order Goal: Emberblock

## Requested Outcome

Build **Emberblock**, a playable, offline, two-dimensional sandbox game that feels like a small
Minecraft. The player opens `index.html` directly from `file://`, lands in a generated block world,
moves and jumps through it, mines and places blocks, collects materials, crafts useful items, builds
something of their own, and returns later to find their world and progress intact. Controls must be
discoverable in the game and documented for later reference.

The intended capability scope is a complete compact survival-sandbox loop: **explore → mine →
collect → craft → build → persist**. The world should be large enough to wander, deep enough to dig,
dark enough at night to make light matter, and stable enough that a reload preserves what the player
changed. Combat, multiplayer, and content-volume parity with Minecraft are outside this pocket-sized
goal; they are not additions to the requested loop.

## Scope, Quality Contract, and Constraints

### User-facing quality contract

1. **Immediate, dependable play.** Opening `index.html` presents a readable first-run screen with a
   visible primary start action and a visible controls/help entry. The game becomes interactive with
   no console error, build step, network request, external library, CDN, font, or asset download.
2. **A world that reads as a world.** A deterministic seeded terrain has rolling hills, layered
   strata, caves, ores, trees, a sky with a day/night cycle, and coherent parallax depth. Blocks look
   deliberately illustrated rather than flat coloured cells. Two materially different visual states
   (day and night, plus underground darkness) are visibly distinct.
3. **A sandbox verb set that actually works.** Walking, jumping, collision, mining with per-block
   hardness and tool speed, block drops, inventory stacking, hotbar selection, placement with reach
   limits, and crafting all complete their advertised action and give visible feedback. Mining and
   placement are never silent no-ops.
4. **Persistence the player can trust.** World edits, inventory, selected slot, player position,
   health, and time of day survive a reload. There is a visible save state, periodic autosave, manual
   save, and a guarded new-world reset. Progress is stored locally and offline.
5. **A small progression with a point.** Wood → planks → sticks → crafting table → wooden pickaxe →
   stone → stone pickaxe → iron is legible through crafting availability, tool speed, and block
   requirements. Torches make caves and night navigable.
6. **Readable, uncluttered interface.** The HUD shows health, time, coordinates, selected item,
   inventory/craft access, and help without covering the player's workspace at the reference
   viewport. Mouse and keyboard controls work together; the canvas is responsive and avoids clipping
   at a 960×600 viewport and a narrow 480px-wide viewport.
7. **A living layer of craft.** Ambient particles, block-break feedback, sound effects generated in
   the browser, subtle screen feedback, and pacing through the day/night cycle make the game feel
   authored. These support the core loop rather than replacing it.

### Comparison target

The concrete reference is **Minecraft's core sandbox loop** (explore, mine, craft, build, and keep
your world). At 2D scale, Emberblock must be recognizably complete at that loop: a new player can find
the controls, gather wood, make a tool, light a cave, place a build, and reload into it. This is a
qualitative floor for feel and loop completeness, not a request for Minecraft's content breadth,
mobs, dimensions, or multiplayer.

### Reference-informed signature challenge

The request names Minecraft, so the credible reference is Minecraft. The decision-changing signature
capabilities are:

- **Block-authored world and building:** the world is made of editable blocks whose removal and
  placement visibly and permanently change it (`must`).
- **Tool-gated material progression:** different materials require the right tool tier, so crafting
  changes what the player can do (`must`).
- **A day/night and underground light rhythm:** darkness changes how the world is navigated and makes
  torches meaningful (`must`).
- **A first-person-feeling survival-sandbox HUD:** health, hotbar, inventory, and crafting are one
  continuous interface (`must`).
- **A compact orientation aid:** coordinates plus a small surface map help the player understand a
  finite handcrafted world (`should`; supports exploration without importing a full mapping system).

Reference-derived content such as mobs, hunger, villages, redstone, and nether dimensions is not
required by this request and is not a binding non-goal; those systems are simply beyond this pocket
scope, and recording them as forbidden would narrow the user's request. The delivered loop must not
be thinned below the signature musts.

### Constraints and exclusions (with provenance)

- Platform: vanilla HTML/CSS/JavaScript, no build step, no package manager, no runtime network access,
  no external libraries, CDNs, fonts, or remote assets (`user`, `project`).
- Must launch and play from `file://`; storage uses browser-local persistence only (`user`).
- Work only inside `/work`; no project Git commit (`user`, `project`).
- English UI, documentation, comments, and work-order text; UTF-8/LF (`project`).
- Preserve the seed's browser/static checks and add project-appropriate tests (`project`).
- No material exclusions beyond the platform constraints above. Features not named by the request are
  neither promised nor forbidden; analysis prioritizes the smallest complete signature loop.

## Acceptance Conditions

1. From a fresh browser profile, opening `index.html` shows a visible Play/Continue action and a
   visible Controls/Help entry, and the game reaches an interactive world without errors.
2. A real pointer and keyboard can move, jump, mine, place, select a hotbar slot, open inventory and
   crafting, craft at least planks, sticks, a torch, a crafting table, and a wooden/stone pickaxe.
3. Mining different blocks takes materially different time, requires the appropriate tool for hard
   ores, drops items into a stackable inventory, and cannot reach beyond the declared range.
4. The player can dig into a cave or wait for night and observe a materially darker state; a placed
   torch visibly lights its surroundings.
5. World edits, inventory, health, selected slot, time, and position survive a page reload; manual
   save and guarded reset are discoverable and work.
6. The reference viewport (960×540 game area) and a narrow viewport (480px wide) keep primary actions,
   help, health, hotbar, and inventory usable without clipping or hidden controls.
7. Seed checks and added tests pass; a headless browser run renders a non-blank, colour-rich canvas
   with the ready status marker. The controls are documented in the game and in `README.md`.
