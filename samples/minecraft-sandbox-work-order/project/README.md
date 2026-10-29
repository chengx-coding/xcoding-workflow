# Terra — a 2D sandbox

Terra is a small, playable 2D sandbox inspired by Minecraft. It is a static page: plain HTML, CSS
and JavaScript with no framework, no build step, no package manager and no network access. Open the
file and the world is already growing.

## Open it

Double-click `index.html`, or open it from a browser with `File → Open`. The page runs from
`file://`; there is no server to start.

## Controls

| Input | Action |
| --- | --- |
| `A` / `D` or `←` / `→` | Walk left and right |
| `Space` or `W` / `↑` | Jump (hold for a higher jump) |
| Left mouse button | Mine the solid block under the pointer within reach; hold to keep mining |
| Right mouse button | Place the selected block in a clear, supported cell |
| `1` – `8` | Select a hotbar material |
| Mouse wheel over the world | Cycle the hotbar |
| `H` | Open or close the field guide (controls and world settings) |
| `P` or `Esc` | Pause and open the field guide |
| `M` | Mute or unmute the synthesized sounds |

The field guide also contains the seed form, the **Surprise me** randomizer, and a two-step
**Reset world** action.

## What the world does

- **Seeded terrain.** A numeric seed grows hills, sandy clearings, dirt and stone strata, caves,
  trees and grass. The same seed always grows the same world; different seeds produce different
  profiles. Change the seed in the field guide to explore another one.
- **A real character.** The explorer falls under gravity, walks, jumps with coyote time and a jump
  buffer, and collides with every solid block on both axes.
- **Mining and building.** Left-click mines a solid block within five blocks; right-click places the
  selected material into an empty cell that has a solid neighbour and does not overlap the explorer.
  Mined blocks refill the hotbar counts; placing spends them.
- **A camera with edges.** The camera follows the explorer smoothly and clamps to the world bounds,
  so the world never scrolls past its own edge.
- **Feedback everywhere.** A pulsing reach outline and ghost placement preview, block-break
  particles, animated walking, small synthesized sounds, toasts for refusals, a live save indicator
  and a clearly lit selected hotbar slot.
- **Offline persistence.** The seed, every mined or placed block, the explorer's position, the
  hotbar selection and the inventory are saved to `localStorage` and restored when the page is
  reopened. If a browser blocks storage for local files, the game falls back to an in-memory store
  for the session and the HUD says so.

## Checks

Run these from this directory:

```console
node --test "tests/**/*.test.js"
python tools/page_check.py
```

`node --test` covers world generation invariants, collision on every axis, jump behaviour,
reach/adjacency/player-overlap placement rules and persistence serialization. `tools/page_check.py`
checks the page is offline, required elements and local assets exist, and then loads the page in
headless Chrome to verify the status marker and a non-blank canvas. Pass `--screenshot <path>` to
keep the captured image.

## Architecture

```text
index.html          page shell: canvas, HUD, hotbar, guide overlay, status marker
css/style.css       full-window layout, HUD, hotbar, overlay and responsive rules
js/config.js        shared constants, block metadata and hotbar order
js/world.js         seeded generation, block access, reach/placement rules, serialization
js/player.js        player state, AABB collision, gravity, movement, jumping, serialization
js/save.js          guarded localStorage adapter, payload validation, memory fallback
js/render.js        camera, sky and parallax, tile textures, character, effects
js/main.js          boot, fixed-step loop, input, hotbar, HUD, audio, autosave
tests/              Node logic tests
tools/page_check.py static and headless-browser checks
```

The status marker is part of the verification contract: `#status` starts at
`data-state="booting"`, becomes `data-state="ready"` after the first successful frame, and becomes
`data-state="error"` if boot or a later runtime step fails.

## Constraints

- No third-party libraries, CDNs, external fonts or network requests.
- Runs from `file://`; no bundler, server or build step.
- Browser modules stay loadable in Node so the logic tests can require them without a DOM.
- Seeded generation keeps the seed snapshot's ground-line contract at column 10, so the original
  world tests continue to pass unchanged.
