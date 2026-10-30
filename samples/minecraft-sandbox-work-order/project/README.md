# Blockstead — a 2D Minecraft-style sandbox

A playable, offline 2D sandbox game inspired by Minecraft. The whole game is this page and its local
files: plain HTML, CSS and JavaScript with no framework, no build step and no network access. Open
`index.html` directly in a browser (double-click it) and play.

## Controls

| Input | Action |
| --- | --- |
| `A` / `D` or `←` / `→` | Move left and right |
| `Space` or `W` | Jump |
| Left click (hold) | Mine the block under the pointer, within reach |
| Right click | Place the selected block in an empty adjacent cell |
| `1` – `9` | Select a hotbar slot |
| Mouse wheel | Cycle the hotbar |
| `P` or `Esc` | Pause and resume |
| `M` | Mute or unmute sound |
| `H` or `?` | Show or hide the controls panel |
| `R` | Return to a safe spot on the surface |

Mining and building are checked for reach, empty cells and stock. A block can never be placed inside
the player. Each hotbar slot shows its remaining stock; mining adds to the matching slot and placing
spends one.

## The world

- Terrain is generated from a numeric seed: hills, layered grass, dirt and stone, sand in the
  valleys, cave pockets and trees. The same seed always rebuilds the same world.
- Type a whole number into the **Seed** field and press **Load** to rebuild the world (or **Random**
  for a fresh one). The current seed is editable at any time.
- A day/night cycle runs continuously; the HUD shows the time of day and the sun, moon and stars
  follow it.
- The camera follows the player and stays inside the world bounds.
- The HUD shows live coordinates and depth, the hovered block and the current phase of the day.

## Saving

Edits, the player position, the hotbar stock and the current time save to `localStorage`
automatically (every few seconds, on pause and when the page is hidden) and are restored the next
time the page opens. If the saved data is unreadable, the page starts a fresh world instead of
failing. Sound and mute preference are stored separately.

## Checks

```console
node --test "tests/**/*.test.js"
python tools/page_check.py
```

`node --test` runs the logic tests; the browser modules are written so they can be required in Node
without a DOM. `python tools/page_check.py` runs the static checks (required elements, local assets,
no network references) and then loads the page in headless Chrome to verify the status marker and a
non-blank canvas. Pass `--screenshot <path>` to keep the captured image.

## Architecture

```text
index.html            page shell: canvas, HUD, hotbar, seed panel, overlays, status marker
css/style.css         visual design, 1280px scaling, reduced-motion rules
js/config.js          constants, block palette, hotbar order, stock and hardness
js/rng.js             seed hashing, PRNG helpers, seed parsing
js/world.js           terrain, caves, trees, block access, spawn search, serialization
js/player.js          gravity, jumping, and block collision
js/camera.js          camera follow and world-bound clamping
js/interaction.js     targeting, reach, mining, placement, inventory and hotbar model
js/daynight.js        day/night clock and sky palette
js/storage.js         versioned localStorage save/load and settings
js/audio.js           procedural WebAudio sound effects and mute
js/ui.js              HUD formatting, key mapping, help content, reduced-motion detection
js/render.js          textured tiles, sky, parallax, particles, player sprite
js/main.js            boot, loop, input wiring, autosave, pause, seed loading
tests/                Node logic and static-page tests
tools/page_check.py   static and headless-browser checks
```

The status marker is part of the verification contract: `#status` starts at `data-state="booting"`,
becomes `data-state="ready"` after a successful first frame, and becomes `data-state="error"` if boot
fails.

## Constraints

- No third-party libraries, CDNs, external fonts or network requests.
- The page runs from `file://`; no bundler or development server is required.
- Browser modules stay loadable in Node for the logic tests.
- Existing tests are never weakened; coverage is added instead.
