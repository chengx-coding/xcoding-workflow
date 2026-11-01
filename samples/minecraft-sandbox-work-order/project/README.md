# Wildgrove — a tiny 2D sandbox

A complete, offline 2D Minecraft-style sandbox in plain HTML, CSS and JavaScript. It is a static page:
no framework, no build step, no package manager, no third-party assets and no network requests.

Open `index.html` directly in a browser (double-click it). Everything works from `file://`.

## What you can do

- Explore a deterministic world generated from a numeric seed: grass, dirt and stone layers, hills,
  dunes, trees and underground caves. The bottom two rows are a sealed bedrock floor that cannot be
  mined, and removing underground blocks exposes a dark cave backdrop rather than the sky.
- Walk and jump with a collidable player that cannot pass through solid blocks or leave the world.
- Mine a block within reach with the left mouse button: the target shows a growing crack
  meter and a pickaxe swing, then breaks into a dust burst with a `+1 <block>` readout.
- Build with the right mouse button into an empty adjacent cell. Placements that would overwrite a
  block, cover the player, float without support, reach too far, or use an empty palette slot are
  refused with a visible explanation.
- Collect per-block counts; every hotbar slot shows how many of that block you are carrying. Mining
  adds, building consumes.
- Choose among nine block types with number keys, the mouse wheel or by clicking the palette.
- Watch a live minimap under the top bar show the world profile, your position and the visible camera
  window as you travel.
- Watch a day/night cycle change the sky, sun/moon, stars and ambient light while the world stays
  readable.
- Pause, mute, and generate a new world from any whole-number seed.
- Reload the page and return to the same world, player position, inventory and clock, restored from
  `localStorage`. An unreadable save is replaced by a fresh world with a visible notice.

The seed is part of the world: `1337` always produces the same terrain, and changing the number
recreates the terrain deterministically.

## Controls

| Input | Action |
| --- | --- |
| `A` / `D` or `←` / `→` | Move left and right |
| `Space` (or `W` / `↑`) | Jump |
| Left click | Mine the block under the pointer, within reach |
| Right click | Place the selected block in an empty adjacent cell |
| `1` – `9` | Select a hotbar slot |
| Mouse wheel | Cycle the hotbar |
| `P` | Pause or resume |
| `M` | Mute or unmute sound |
| Seed field + `New world` | Generate a world from a whole-number seed |

## Run and verify

Open the page:

```console
start index.html        # Windows; or double-click index.html
```

Run the logic tests (Node 18+):

```console
node --test "tests/**/*.test.js"
```

Run the static and headless-browser page check:

```console
python tools/page_check.py
python tools/page_check.py --screenshot capture.png     # keep the screenshot
```

Run the automated journey probe (Node 22+ with a local Chrome; drives the real page over the
DevTools protocol):

```console
node tools/journey_check.js --out tmp/journeys
```

It executes mining, placement and every refusal, reload persistence, corrupt-save recovery, pause,
day/night, boundary clamping and hotbar selection, saves screenshots under `--out`, and writes
`journey-report.json`.

## Architecture

```text
index.html            page shell: canvas, top bar, HUD, hotbar, toasts, pause overlay, status marker
css/style.css         visual design, responsive 1280px layout, reduced-motion support
js/config.js          block catalogue, palette order, physics, time, save and starter-kit constants
js/rng.js             deterministic hash, mulberry32 and value-noise helpers
js/world.js           seeded terrain, trees, dunes, caves, block access, JSON/RLE serialization
js/player.js          axis-separated AABB physics with sub-stepping, jump and grounding
js/inventory.js       per-block counts, add/consume with a non-negative invariant
js/interaction.js     mining and placement rules with structured refusal reasons
js/persistence.js     versioned localStorage payload with corruption and version fallbacks
js/timecycle.js       day clock, phases, sky colours and light level
js/camera.js          eased follow camera clamped to the world bounds
js/render.js          canvas presentation: sky, parallax hills, textured blocks, player, particles,
                      crack/pickaxe break animation and the minimap renderer
js/ui.js              presentation model helpers: hotbar, coordinates, clock and target text
js/audio.js           lazy WebAudio sound cues with mute
js/main.js            boot, input, loop, saving, status marker and the probe surface
tests/                Node logic tests (terrain, physics, interaction, persistence, render, UI, ...)
tools/page_check.py   static and headless-browser page checks
tools/journey_check.js automated browser journey probe
```

The browser files are classic UMD scripts so the same logic modules load in Node for tests without a
DOM. `window.__sandbox` exposes a small read/command probe surface used only by the automated browser
checks; the page itself never depends on it.

The `#status` element keeps its contract: `data-state="booting"` before the first frame,
`data-state="ready"` after a successful frame, and `data-state="error"` (red) if boot or a runtime
error fails.
