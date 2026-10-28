# Sandbox (sample consumer project)

A playable, offline 2D sandbox game inspired by Minecraft. It is built from plain HTML, CSS and
JavaScript with no framework, no build step, no third-party libraries and no network requests.

The world is generated deterministically from a numeric seed: a flat spawn meadow opens into rolling
hills, with grass, dirt and stone layers plus trees that provide wood. The player can walk, jump, mine
blocks within reach and place blocks from the hotbar. The camera follows the player, and the world and
player state are saved to `localStorage` and restored the next time the page is opened.

## Open it

Open `index.html` directly in a browser (double-click it), or serve the folder with any static file
server. The page works from `file://`; there is nothing to install or build.

## Controls

| Input | Action |
| --- | --- |
| `A` / `D` or `←` / `→` | Move left and right |
| `Space` | Jump |
| Left click | Mine the block under the pointer, within reach |
| Right click | Place the selected block in an empty adjacent cell |
| `1` – `4` | Select a hotbar block |
| Click a hotbar slot | Select that block |

The selected hotbar slot is highlighted, and the HUD shows the selected block. The page hint line
repeats the controls while playing.

## Saving

Mining, placing, selecting a block and moving the player are saved through `localStorage`. The save
contains the full block array, the world seed, the player position and velocity, and the selected
block. A missing, corrupt or unavailable save falls back to a freshly generated world; a save written
by this version stores `version: 1`.

## Checks

```console
node --test "tests/**/*.test.js"
python tools/page_check.py
```

`node --test` runs the logic tests. They cover terrain determinism and layers, bounded block access,
player landing/wall/jump collision, reach and placement rules (including the player footprint),
camera clamping, and save/load round-tripping. `tools/page_check.py` checks that the page has no
external network references, that its required elements and local assets exist, and then loads it in
headless Chrome. It verifies that the `#status` marker turns green and that the canvas renders more
than a blank frame. Pass `--screenshot <path>` to keep the captured image.

## Architecture

```text
index.html          page shell: canvas, HUD hint, hotbar, status marker
css/style.css       layout, hotbar selected state, status-marker colours
js/config.js        shared constants (seed, world size, tiles, physics, block ids, hotbar)
js/world.js         seeded terrain, trees, block access, serialization
js/player.js        player state, AABB movement, collision, gravity and jumping
js/interaction.js   pointer mapping, reach, mining and placement rules
js/save.js          versioned localStorage save/load with an injectable storage
js/render.js        camera follow/clamp, tile and player rendering
js/main.js          boot, fixed-step loop, input, hotbar, HUD and persistence
tests/              Node logic tests
tools/page_check.py static and headless-browser checks
```

The modules use the same UMD wrapper as the seed so Node can require them without a DOM. `world.js`
keeps a flat spawn plateau over the original ground line and blends into seeded hills east of it. The
player is a small AABB moved in substeps; horizontal and vertical collisions snap to tile edges, and
out-of-world sides act as solid walls. `main.js` runs a fixed 60 Hz update step, recomputes the camera
from the player position, and renders only the visible tiles.

The status marker is part of the verification contract: `#status` starts at
`data-state="booting"`, becomes `data-state="ready"` after a successful first frame, and becomes
`data-state="error"` (red) if boot or a later frame fails. `tools/page_check.py` samples the marker's
pixel.

## Constraints

- No third-party libraries, CDNs, external fonts or network requests.
- The page stays runnable from `file://`.
- The modules stay loadable in Node for the logic tests.
- The seed tests in `tests/world.test.js` remain unchanged; new coverage lives in the added test
  files.
