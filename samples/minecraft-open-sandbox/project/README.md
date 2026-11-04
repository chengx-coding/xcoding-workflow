# Blockfall — a small offline 2D sandbox

Blockfall is a playable, side-view block sandbox inspired by Minecraft. It runs by opening
`index.html` directly from disk. There is no build step, no package manager, no framework, no
external library, no CDN, no external font, and no network request at runtime. All art and audio are
generated procedurally in the browser.

You spawn on a generated island, punch trees, mine downward into caves, build with the blocks you
collect, craft better tools, smelt ore, survive hostile nights, and come back later to the same world.

## Quick start

1. Open `index.html` in a modern browser (Chrome, Edge, Firefox, or Safari).
2. Click **New World** (or **Continue** if a save exists).
3. Punch a tree with **left click**, then press **E** to craft planks and sticks.
4. Craft a crafting table, place it, and stand near it to unlock tools.

No local server is required. The game is a set of classic scripts, so it works from `file://`.
Progress is saved in the browser's `localStorage`; the pause menu also offers portable
export/import files if storage is unavailable or you want a backup.

## Controls

| Input | Action |
| --- | --- |
| `A` / `D` or `Left` / `Right` | Walk |
| `Space`, `W`, or `Up` | Jump · swim upward · climb a ladder |
| `S` or `Down` | Climb down a ladder |
| `Shift` | Sprint (costs extra hunger) |
| Left mouse (hold) | Mine the targeted block; repeated clicks attack a mob |
| Right mouse | Place the selected block · use a table/furnace · eat held food |
| `1`–`9` or mouse wheel | Select a hotbar slot |
| Click a hotbar slot | Select that slot |
| `E` | Open/close inventory and crafting |
| `H` | Open/close in-game help |
| `M` | Show/hide the minimap |
| `Esc` | Pause, save, settings, export/import |
| `Enter` (title) | Continue, or start a new world if there is no save |

Inventory: click a stack to pick it up, click a slot to place it, right-click to split/place one,
Shift-click to quick-move between the hotbar and storage. Close a panel with `E`, `Esc`, or its button.

## What is in the game

### World

- A deterministic 320 × 96 tile island generated from a numeric seed: rolling hills, a pond and
  shoreline, caves, coal and iron veins, oak trees, flowers, and tall grass.
- A side-view camera with layered sky, sun/moon, stars, clouds, distant hills, animated water, cave
  backdrops, and pixel-art block textures with variants.
- A day/night cycle (10 real minutes per day) with a light map: daylight on the surface, darkness in
  caves, warm light from torches and active furnaces.
- A local minimap with surface/cave colours, the player marker, mobs, and a `DAY`/`NIGHT` label.

### Mining and building

- Every block has a hardness and a preferred tool. A matching pickaxe/axe/shovel mines substantially
  faster; hand mining is possible but slow.
- Blocks drop items directly into the inventory, with a full-inventory warning.
- Placement requires a neighbouring block, cannot intersect the player, and torches/flowers need
  ground beneath them. Breaking a furnace also removes its stored contents.

### Inventory and crafting

- 36 slots total: a 9-slot hotbar plus 27 storage slots, with stack limits, split, swap, and
  Shift-click quick move.
- 16 recipes: planks, sticks, crafting table, torches, furnace, wooden/stone/iron pickaxes, axes and
  swords, ladders, and stone bricks. Table recipes are locked until a crafting table is within a few
  blocks; the crafting panel tells you whether one is in range.
- Tools change mining speed and melee damage. Tools do not have durability in this small sandbox.

### Furnace

- Place a furnace and right-click it to open the smelting panel.
- Put raw iron, sand, or raw porkchop in the top slot and coal, planks, logs, sticks, or ladders in
  the fuel slot.
- Fuel burns for a material-specific time; each item takes 5 seconds to smelt. The panel shows the
  flame, progress, and output. Take the output like an inventory slot.

### Survival

- 20 health (10 hearts), 20 hunger (10 pips), and 10 air bubbles while underwater.
- Sprinting, walking, and mining drain exhaustion; hunger drains, and high hunger slowly regenerates
  health. An empty stomach causes starvation damage.
- Falling more than three blocks hurts; deep water drowns you after your air runs out.
- Pigs and chickens wander the surface. Zombies and slimes spawn at night, chase you, and hit on
  contact. Left-click attacks with the held tool; kills drop food, slimeballs, or rotten flesh.
- Death keeps your world and inventory. Respawn at the world spawn with full health and hunger.

### Saving

- The world, player position/stats, inventory, selected slot, time of day, furnace contents, settings,
  and seed are saved.
- Autosave runs every 20 seconds while playing, when the tab is hidden, when the page is closed, when
  you pause, and when you return to the title.
- **Continue** on the title restores the save. **Save now** in the pause menu confirms a manual save.
- **Export save** downloads a JSON file; **Import save** restores one. This is the fallback when a
  browser blocks `localStorage` for `file://` pages; the game keeps the session in memory and warns
  you instead of failing.
- If a stored payload is corrupt or from an unsupported version, the game starts a fresh world and
  shows the reason on the title instead of freezing.

## First ten minutes

1. Punch a nearby tree until you have a few logs.
2. Press `E`, craft **Oak Planks** four times, then **Sticks** twice, then a **Crafting Table**.
3. Close the inventory, select the table, and right-click a supported empty cell to place it.
4. Stand next to the table, press `E`, and craft a **Wooden Pickaxe**.
5. Mine stone and coal. Craft a **Furnace** at the table with 8 stone.
6. Place the furnace, right-click it, and smelt raw iron with coal.
7. Craft a better pickaxe or sword, place torches in caves, and build a shelter before night.
8. At night, fight or stay inside. Keep an eye on hearts and hunger; eat apples or cooked porkchop.

## Verification

From the project root:

```console
node --test "tests/**/*.test.js"
python tools/page_check.py
node tools/play_check.mjs --full
```

- `node --test` covers RNG/worldgen, block access/serialization, AABB physics, mining, placement,
  inventory, every recipe, smelting, save round-trip/corruption, lighting, mobs/combat, and survival.
- `python tools/page_check.py` checks the static page (required ids, local assets, no network
  references), launches headless Chrome with an isolated profile, verifies the green status marker and
  a non-blank canvas, and can keep a screenshot with `--screenshot <path>`.
- `node tools/play_check.mjs --full` is a dependency-free Chrome DevTools Protocol scenario: title →
  new world → walk → mine → inventory → craft → place table → craft pickaxe → save/reload → furnace
  smelt → night → help → ten real pointer clicks → death/respawn → 1280×720 layout → corrupt-save
  fallback. It uses trusted input events and writes screenshots under its `--out` directory.

## Project layout

```text
index.html          page shell, HUD, hotbar and all menu panels
css/style.css       pixel-UI styling, responsive layout and status marker
js/config.js        frozen constants, block/item registry, tool tiers
js/rng.js           deterministic hash, mulberry32, value noise and fbm
js/world.js         worldgen, block access, spawn and serialization
js/textures.js      procedural 16x16 block textures and item icons
js/inventory.js     stack core, hotbar and slot operations
js/crafting.js      recipes, table gating and safe crafting
js/furnace.js       furnace state, fuel and timed smelting
js/save.js          RLE world encoding, payloads and storage adapter
js/player.js        AABB physics, reach, mining and placement rules
js/survival.js      health, hunger, air, fall damage and regeneration
js/entities.js      passive/hostile mob spawning, AI, combat and drops
js/lighting.js      tile light map, torch/furnace glow
js/particles.js     break/place/damage particles
js/audio.js         procedural WebAudio sounds
js/minimap.js       local minimap and day/night label
js/render.js        sky, parallax, tiles, characters, effects and selection
js/input.js         keyboard/pointer/wheel state
js/ui.js            inventory, crafting and furnace panels
js/main.js          boot, fixed-step loop, interaction, HUD and persistence
tests/              Node logic tests
tools/page_check.py static + headless-browser smoke check
tools/play_check.mjs dependency-free CDP play/visual scenario
```

## Offline and accessibility notes

- There is no `fetch`, `XMLHttpRequest`, WebSocket, remote image, remote font, or audio file in the
  product. Every texture and sound is generated from code.
- Menus are native DOM buttons, labels, and inputs with focus styles. The HUD uses `aria-live` for
  toasts, the canvas has an accessible label, and the help panel is a text alternative to the canvas.
- `prefers-reduced-motion` is respected, and the pause menu has a reduce-motion toggle that limits
  particles and screen shake.
- The game is designed for a 960 × 540 play area and scales the stage while keeping the aspect ratio;
  it remains usable at 1280 × 720 and smaller desktop windows.

## Scope choices

This is deliberately a **small** Minecraft-like sandbox, not a clone. Multiplayer, 3D, redstone, the
Nether/End, villagers, and mods are out of scope. Within the chosen scope, the game favors a complete
mine → craft → build → survive → save loop over content volume. Tools have no durability and the world
is a single continuous map rather than chunks; both choices keep the save format and tests simple.
