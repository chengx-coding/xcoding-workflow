# Blockhaven — a small 2D Minecraft

Blockhaven is a playable, offline 2D block sandbox inspired by Minecraft. It runs in one page with
plain HTML, CSS and JavaScript: no build step, no framework, no external library, no CDN, no font and
no network request. Open `index.html` directly from the file system and play.

The game is a compact side-view block world: explore generated terrain, mine blocks, collect what you
break, craft better tools, place blocks, light the dark with torches, and come back to the same world
after a reload.

## Run it

1. Open `index.html` in a current desktop browser (the automated checks use Chrome or Edge).
2. Click once in the page so the browser allows audio.
3. Play. Progress saves automatically.

The page is designed for `file://`. No server is required, and nothing is fetched from the network.

## Controls

| Keys | Action |
| --- | --- |
| <kbd>A</kbd> / <kbd>D</kbd> or <kbd>Left</kbd> / <kbd>Right</kbd> | Move left and right |
| <kbd>W</kbd>, <kbd>Space</kbd> or <kbd>Up</kbd> | Jump, or swim up in water |
| Left mouse (hold) | Mine the highlighted block |
| Right mouse | Place the selected hotbar block |
| <kbd>1</kbd> – <kbd>8</kbd> | Select a hotbar slot |
| Mouse wheel | Cycle hotbar slots |
| <kbd>E</kbd> | Open or close crafting |
| <kbd>H</kbd> or <kbd>F1</kbd> | Open or close the in-game controls |
| <kbd>Esc</kbd> | Pause; in a menu, close it |
| <kbd>M</kbd> | Mute or unmute audio |

The same list is available in the game's help overlay, opened with <kbd>H</kbd> or from the pause menu.

## What is in the game

- **A generated block world.** A 192 × 96 tile world with rolling surface terrain, dirt and stone
  layers, caves and surface shafts, coal and crystal ore, trees, sandy patches and shallow lakes.
  Every new world gets a random seed; the seed is shown in the pause menu.
- **Mining and building.** Blocks within reach are highlighted. Hold the left button to break a block
  with a visible crack progression; broken blocks drop into the inventory. Right-click places the
  selected hotbar block into a reachable empty or water tile.
- **Inventory and hotbar.** Eight block slots with counts, selected with the number keys, the mouse
  wheel, or a click on the slot.
- **Crafting and progression.** Press <kbd>E</kbd> to craft:
  - 1 wood → 4 planks
  - 2 planks → 4 sticks
  - 1 stick + 1 coal → 4 torches
  - 3 planks + 2 sticks → wooden pickaxe
  - 3 stone + 2 sticks → stone pickaxe

  Wood, dirt, sand, leaves, torches and crystal can be worked by hand. Stone and coal need a wooden
  pickaxe; crystal needs a stone pickaxe and glows when placed. Tools do not wear out.
- **Day and night.** A 4-minute cycle changes the sky, the sun and moon, and the available skylight.
  Darkness hides caves and distant terrain; torches and crystal ore light it again.
- **Saving.** The world (including every edit), inventory, player position, time of day and day count
  are saved to `localStorage` under `small-minecraft-save-v1`. The game autosaves changes every eight
  seconds and also saves when you pause and choose **Save now**, when the page becomes hidden, and
  before it unloads. A missing save starts a fresh world; an unreadable save falls back to a fresh
  world with a visible message instead of breaking the page. **New world** in the pause menu asks for
  confirmation.
- **Presentation.** Procedurally drawn block textures, a blocky animated character, break and place
  particles, a day/night sky, parallax hills, clouds, water, torches, synthesized sound effects, a
  crafting panel, a pause menu and an in-game control list.

### Deliberate scope

The work order's analysis chose a peaceful creative-survival hybrid focused on mining, building,
exploring and crafting. These Minecraft systems are deliberately **not** in this small game: health,
hunger, fall damage and death; hostile mobs and combat; redstone or other mechanisms; multiplayer;
3D; infinite or streamed worlds; flowing liquids, farming, animals, villages and dimensions. The
reasoning and the re-entry trigger are recorded in the work order's `analysis.md` and `solution.md`;
they are scope decisions, not claims that those systems are unimportant.

## Verification

Run from the project root:

```console
node --test "tests/**/*.test.js"
python tools/page_check.py
node tools/browser_check.mjs
```

- `node --test "tests/**/*.test.js"` runs the unit suites: world generation invariants (including the
  legacy seed-contract anchor), player physics and collision, mining rules, inventory, crafting,
  lighting and save/corruption handling, plus the original seed tests.
- `python tools/page_check.py` performs the static page check (required elements, local assets, no
  network references) and a headless-Chrome screenshot check (green status marker, non-blank canvas).
  `--screenshot <path>` keeps the capture.
- `node tools/browser_check.mjs` launches headless Chrome through the DevTools Protocol and drives the
  real game with real keyboard and mouse events. It asserts boot, no remote requests, movement,
  jumping, mining a tree, crafting planks, placing a block, the help overlay, pause/save, reload
  persistence, day/night lighting, responsive pointer mapping, mute feedback and new-world creation,
  and it fails on any console error. Pass `--screenshots <dir>` to keep its captures.

The browser check is a test tool, not part of the game: it needs Node 22 or newer (for the built-in
`WebSocket`) and a local Chrome or Edge installation.

## Layout

```text
index.html            page shell and overlay markup
css/style.css         layout, canvas scaling, HUD, hotbar and overlay styling
js/config.js          constants, block/item/tool/recipe definitions, palette, controls
js/world.js           seeded generation, block access, JSON and RLE codecs
js/player.js          fixed-step movement, collision, jump, swimming, respawn
js/mining.js          reach, tool rules, break times, drops, mining progress
js/inventory.js       item counts, hotbar slots and selection
js/crafting.js        recipe affordability and atomic crafting
js/lighting.js        skylight/torch/crystal light propagation and day phases
js/save.js            versioned snapshots, validation, localStorage adapter
js/audio.js           synthesized sound effects and mute
js/input.js           keyboard/pointer state and canvas coordinate mapping
js/render.js          textures, sky, world, lighting, player, particles, target feedback
js/ui.js              HUD, hotbar, help/pause/craft panels, toasts, save indicator
js/main.js            boot, fixed-step loop, interactions, saving, test surface
tests/                unit suites (seed contract plus game logic)
tools/page_check.py   static and headless-browser page check
tools/browser_check.mjs interactive DevTools-Protocol check
```

All assets are local code; there are no image, audio or font files to load.
