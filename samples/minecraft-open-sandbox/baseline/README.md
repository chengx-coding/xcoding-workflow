# Blockhaven

A small, offline 2D sandbox game inspired by Minecraft. The world is generated from a
seed, you can mine and build anywhere, craft tools and lights, survive hungry nights,
and everything you change is saved in your browser.

Open `index.html` directly — no server, build step, libraries, accounts, or network
connection are required.

## Controls

| Input | Action |
| --- | --- |
| `A` / `D` or arrow keys | Move left / right |
| `W`, `Space`, or up arrow | Jump |
| `Shift` | Sprint (hold while using a table/furnace to place a block instead) |
| Mouse | Aim and choose a block within reach |
| Left click / hold | Mine the targeted block, or attack a mob |
| Right click | Place the selected block, eat the selected food, or use a table/furnace |
| `1`–`9` | Select a hotbar slot |
| Mouse wheel | Cycle hotbar slots |
| `E` | Open inventory and crafting (also closes it) |
| `R` | Use a nearby furnace (or close its screen) |
| `Q` | Drop one of the selected item |
| `M` | Mute / unmute sound |
| `Esc` | Pause, or close the current screen |
| `Enter` | Start / continue from the title screen, or respawn after death |

### Inventory

- **Left click** a slot to pick up a stack, then click another slot to put it down.
- **Right click** picks up half a stack, or places a single item from the held stack.
- **Shift-click** moves a stack between the backpack and the hotbar.
- Click a **recipe card** to craft it. Recipes marked `table` require a placed
  crafting table within a few blocks. Hold `Shift` while clicking a recipe to craft
  as many as the available materials allow.

## The first day

1. Hold left click on a tree trunk until it breaks.
2. Press `E`. Craft **Oak Planks** from logs, then **Sticks** from planks, then a
   **Crafting Table**.
3. Place the table with right click. With the table nearby, craft a **Wooden Pickaxe**.
4. Mine stone and coal. Coal and a stick make **Torches**.
5. Build a shelter before sunset. Zombies only appear in the dark at night.
6. Eat apples or cook pork in a **Furnace** to keep your hunger up. You regenerate
   health while well fed and resting.

## World and survival

- **Biomes:** meadows, forests, and deserts (with cacti), rolling hills, and deep caves.
- **Ores:** coal (any pickaxe), iron (stone or better), gold and diamond (iron or better).
- **Crafting:** planks, sticks, torches, tables, furnaces, stone bricks, glow lamps,
  wood/stone/iron/diamond tools, swords, axes, and golden apples.
- **Smelting:** iron ore, gold ore, sand, raw pork, cobblestone, and logs can be
  smelted in a furnace with coal or charcoal.
- **Mobs:** passive pigs drop pork. Zombies appear after dark, chase you, and burn in
  morning sunlight. A sword deals more damage; left click a mob to fight.
- **Light:** daylight floods the surface and fades into caves. Torches, glow lamps,
  and furnaces emit warm block light. The world becomes genuinely dark at night.
- **Death:** your pockets stay safe; you wake at your spawn point.

## Saving

- The game autosaves every few seconds while you play, when you pause or quit to the
  title, and when the page is hidden or closed.
- The **Continue World** button appears on the title screen when a save exists.
- Progress lives in `localStorage` under `blockhaven.save.v1` (settings under
  `blockhaven.settings.v1`). It stays on the device and never uses the network.
- A new world replaces the current save. Use a seed to recreate a world later.

## Files

- `index.html` — the game shell and all screens.
- `css/game.css` — pixel interface styling.
- `js/data.js` — blocks, items, recipes, procedural textures, and synthesized audio.
- `js/world.js` — seeded terrain, caves, ores, lighting, and save deltas.
- `js/game.js` — simulation, player, mobs, rendering, UI, and persistence.

All art, sound, and world data are generated locally in the browser. There are no
external assets or dependencies.
