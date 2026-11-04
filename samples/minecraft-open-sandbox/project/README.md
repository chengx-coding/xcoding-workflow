# Emberblock

Emberblock is a playable, offline, 2D block sandbox inspired by Minecraft. You spawn in a generated
valley, gather wood, craft tools, dig into caves, light the dark, build something, and come back to it
later. All art, sound, and world data are generated locally by the page.

Open `index.html` directly in a modern browser. There is no build step, package manager, server,
external library, CDN, web font, or network request. Emberblock is designed for a landscape window.

## First steps

1. Open `index.html`. Choose **Play** (or **Continue** if a save exists).
2. Hold the left mouse button on a tree to gather logs.
3. Press **E** to open your pack. Craft planks, sticks, and a crafting table.
4. Put the table in the hotbar, select it, and right-click solid ground to place it.
5. Stand near the table, craft a wooden pickaxe, and mine stone.
6. Craft a furnace, place it nearby, and smelt raw iron into ingots.
7. Place torches in caves or around your build. Press **Esc** to pause.

The first-run **How to Play** panel and the in-game **First Steps** strip repeat the essentials.

## Controls

| Input | Action |
| --- | --- |
| `A` / `D` or `鈫恅 / `鈫抈 | Move |
| `W`, `Space`, or `鈫慲 | Jump |
| `Shift` | Sprint |
| Hold left mouse | Mine / break the targeted block |
| Right mouse | Place the selected block; open a targeted crafting table or furnace |
| Middle mouse | Pick a targeted block from your pack into the hotbar |
| `1`鈥揱9` | Select a hotbar slot |
| Mouse wheel | Cycle hotbar slots |
| `E` | Open or close the pack and crafting screen |
| `H` or `?` | Open the controls panel |
| `M` | Show or hide the surface map |
| `Ctrl+S` (or `Cmd+S`) | Save now |
| `Esc` | Close the current panel, or pause the game |

In the pack: click a stack to pick it up, click another slot to place or swap, right-click to take
half or place one, and Shift-click to move a stack between the pack and hotbar. `E` closes the pack.

## The world

- A deterministic 320 脳 144 tile world with rolling surface terrain, layered soil and stone, winding
  caves, coal and iron deposits, oak trees, flowers, and tall grass.
- A day/night cycle with moving sun, moon, stars, parallax hills, and drifting clouds.
- Sky light, depth shadow, and torch light. Caves and night are materially darker than the surface.
- Fall damage, ten hearts, slow regeneration, death, and respawn with your pack retained.
- A finite world with a surface minimap and live coordinates.

### Blocks and progression

| Material | Where it comes from | What it unlocks |
| --- | --- | --- |
| Wood | Oak trees, by hand | Planks, sticks |
| Planks / crafting table | Hand recipes | Tools, furnace, stone bricks, torches |
| Coal | Coal ore, needs a wooden pickaxe | Torches, furnace fuel |
| Cobblestone | Stone, needs a wooden pickaxe | Stone pickaxe, furnace, stone bricks |
| Raw iron | Iron ore, needs a stone pickaxe | Iron ingots at a furnace |
| Iron ingot | Raw iron + coal in a nearby furnace | Iron pickaxe |
| Sand / glass | Surface sand, smelted at a furnace | Windows and decorative builds |

Hard blocks enforce pickaxe tiers. A wooden pickaxe mines stone and coal; a stone pickaxe mines iron;
an iron pickaxe is the fastest. Recipes that need a station are clearly marked **Locked** with the
missing station or ingredient shown instead of silently doing nothing.

### Save data

Progress is stored in this browser's local storage under `emberblock.save.v1`: the seed, compact
world edits, pack, selected slot, position, health, time of day, stats, tutorial progress, and sound
setting. The game autosaves after changes and on a 12-second cadence, and also saves when the page is
hidden. `Ctrl+S` saves immediately. Corrupt or incompatible data is discarded with a visible notice
and a fresh world is started; the page never fails to boot because of bad save data.

**New World** always asks for confirmation from the pause menu and from the title when a saved world
exists. It erases the local save only after you confirm.

## Project layout

```text
index.html          page shell, HUD, overlays, dialogs
css/style.css       layout, responsive rules, visual identity
js/config.js        blocks, items, recipes, tuning constants
js/rng.js           seeded PRNG and deterministic noise
js/world.js         terrain, caves, ores, trees, light field, save diffs
js/inventory.js     stacking, transfers, station checks, crafting
js/physics.js       AABB collision, movement, jumping, fall damage
js/save.js          versioned save encoding, validation, fallback
js/textures.js      procedural block textures and item icons
js/audio.js         procedural WebAudio feedback
js/render.js        sky, parallax, tiles, lighting, player, particles, map
js/ui.js            HUD, overlays, inventory, recipes, toasts, focus
js/main.js          game loop, input, interaction, persistence, state
tests/              pure-module tests run by Node
tools/page_check.py seed static and headless-browser check
tools/cdp_client.py standard-library Chrome DevTools Protocol helper
tools/play_probe.py automated real-browser product probe
```

## Verification

```console
node --test "tests/**/*.test.js"
python tools/page_check.py
python tools/play_probe.py --page index.html
```

`page_check.py` verifies the required page IDs, that every local asset resolves, that no network
asset is referenced, that the ready marker is green, and that the canvas is colour-rich.
`play_probe.py` launches headless Chrome through the standard library and exercises a real Play click,
movement, mining, crafting, persistence, help/inventory overlays, and a narrow viewport. It writes
screenshots and a JSON report under `playcheck/` when no `--out` is supplied.

In a restricted container Chrome may be unable to create its default profile directory. Point
`HOME` at a writable directory before running either check, for example:

```console
HOME="$PWD/.tmp/home" python tools/page_check.py
```

The game itself performs no network requests. The optional CDP probe only talks to the locally
launched headless Chrome debugging port. The game remains playable from `file://`.

