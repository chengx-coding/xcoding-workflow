# Verdant Depths — a pocket sandbox

A playable, offline 2D sandbox inspired by Minecraft. This is a static page built from plain HTML,
CSS and JavaScript: no framework, no build step, no package manager and no network access. Open
`index.html` directly in a browser to play from `file://`.

The world is generated from a numeric seed and saved to `localStorage`, including edits, player
position, selected block, time of day and progress. Reopening the page restores the valley exactly
where you left it. A corrupt or incompatible save is discarded safely and a fresh world is grown.

## Open it

Double-click `index.html`, or open it with any modern desktop browser. Sound starts after the first
interaction because browsers require a user gesture before audio.

## Controls

| Input | Action |
| --- | --- |
| `A` / `D` or `←` / `→` | Walk left and right |
| `Space` | Jump; hold for a higher arc |
| `Shift` | Sprint |
| Left click | Mine the outlined block within reach |
| Right click | Place the selected block in the green outlined cell |
| `1` – `9` | Select a hotbar block |
| Mouse wheel | Cycle the hotbar |
| `H` | Open or close the field manual |
| `M` | Mute or restore generated sound |
| `Esc` | Close the field manual or world loom |

Blocks can only be placed in empty, reachable cells with a solid neighbour, and never inside the
player. The deep bedrock at the bottom of the world cannot be mined.

Use the **Seed** chip or **New world** button to open the world loom. Enter a numeric seed, choose a
preset, or let it surprise you. Generating a new world replaces the current save.

## What is in the valley

- Seeded rolling terrain with meadow, woodland and dune biomes, caves, coal seams, prism crystals,
  grass, dirt, stone, timber and canopy trees.
- Nine placeable block types: meadow grass, rich dirt, slate stone, timber, canopy leaves, warm sand,
  oak planks, sun glass and glow lanterns.
- A player with gravity, acceleration, sprinting, variable-height jumping, coyote time and solid
  collision.
- Reach-limited mining and face-aware placing, with a live target outline and block ghost.
- A clamped, smoothly following camera; a minimap; a day/night cycle with stars, parallax ridges,
  drifting clouds, lantern and crystal light, fireflies and break/place particles.
- Four field notes that track mining, building, crystal discovery and exploration.
- Autosave feedback, a generated soundscape, and a built-in field manual.

## Checks

From this directory:

```console
node --test "tests/**/*.test.js"
python tools/page_check.py
```

`node --test` runs the logic tests for terrain generation, serialization, player physics, block
interaction, camera bounds and save handling. `tools/page_check.py` verifies required page elements,
local assets, the absence of network references, then loads the page in headless Chrome, checks the
status marker and samples the rendered canvas. Pass `--screenshot <path>` to keep a captured image.

## Architecture

```text
index.html          page shell, HUD, hotbar, field manual and seed dialog
css/style.css       visual system, layout, selected-slot state and motion
js/config.js        world size, physics, block ids, hotbar and save constants
js/world.js         seeded terrain, biomes, caves, ores, trees, spawn and serialization
js/player.js        gravity, movement, jump handling and axis-separated collision
js/interaction.js   reach checks, target inspection, mining and face-aware placement
js/camera.js        follow smoothing, world-bound clamping, shake and coordinate mapping
js/storage.js       versioned save payloads and safe localStorage access
js/render.js        sky, terrain textures, player, particles, lighting, minimap and icons
js/main.js          boot, input, game loop, HUD state, saves, hotbar and dialogs
tests/              Node logic tests
tools/page_check.py static and headless-browser checks
```

The status marker is part of the verification contract: `#status` starts at
`data-state="booting"`, becomes `data-state="ready"` after the first successful frame, and becomes
`data-state="error"` if boot fails.

## Constraints

- No third-party libraries, CDNs, external fonts, remote images or network requests.
- The page works from `file://` and needs no development server.
- Browser modules remain loadable in Node for the logic tests.
- Text files are UTF-8 with LF line endings and JavaScript keeps two-space indentation.
