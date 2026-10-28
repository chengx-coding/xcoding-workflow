# Sandbox (sample consumer project seed)

This is the seed snapshot for the XC work-order sample: the consumer project's state before the
managed work order ran. The finished game is in [`../project/`](../project/); this directory exists so
the task can be run again from a reproducible starting point.

The seed is a static, offline 2D sandbox shell: plain HTML, CSS and JavaScript, no framework, no build
step, no network. The page boots, renders a flat placeholder world, and reports a green status
marker. Movement, collision, mining, building, camera input and persistence are deliberately not
implemented; the managed work order owns them.

## Open it

Open `index.html` directly in a browser (double-click it). The page must work from `file://`.

## Checks

```console
node --test "tests/**/*.test.js"
python tools/page_check.py
```

`node --test` runs the skeleton's logic tests. `tools/page_check.py` checks that the page has no
external network references, that its required elements and local assets exist, and then loads it in
headless Chrome to verify the status marker and a non-blank canvas. Pass `--screenshot <path>` to
keep the captured image.

## Architecture

```text
index.html          page shell: canvas, HUD, hotbar, status marker
css/style.css       layout and status-marker colours
js/config.js        shared constants (world size, tile size, physics, block ids)
js/world.js         world data, block access, serialization
js/player.js        player state and a placeholder movement step
js/render.js        camera and canvas rendering
js/main.js          boot, status marker and frame loop
tests/              Node logic tests
tools/page_check.py static and headless-browser checks
```

The status marker is part of the verification contract: `#status` starts at
`data-state="booting"`, becomes `data-state="ready"` after a successful first frame, and becomes
`data-state="error"` if boot fails.

## Target controls

| Input | Action |
| --- | --- |
| `A` / `D` or `←` / `→` | Move left and right |
| `Space` | Jump |
| Left click | Mine the block under the pointer, within reach |
| Right click | Place the selected block in an empty adjacent cell |
| `1` – `4` | Select a block in the hotbar |

## Constraints

- No third-party libraries, CDNs, external fonts or network requests.
- Keep the page runnable from `file://`.
- Keep the modules loadable in Node for the logic tests.
- Do not weaken the existing tests; add coverage instead.
