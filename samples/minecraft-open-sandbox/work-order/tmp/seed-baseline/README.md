# 2D sandbox starter

This is a minimal, offline HTML/CSS/JavaScript sandbox shell. It boots, renders a flat placeholder world, and reports a page status. Movement, mining, building, crafting, progression, saving and UI are for the implementation to decide.

Open `index.html` directly in a browser. The page must work from `file://` with no build step, external libraries, CDNs, fonts or network access.

## Checks

```console
node --test "tests/**/*.test.js"
python tools/page_check.py
```

`page_check.py` checks the static page and loads it in headless Chrome; `--screenshot <path>` keeps a capture.

## Layout

```text
index.html          page shell: canvas, HUD, hotbar, status
css/style.css       layout and status colours
js/config.js        shared constants
js/world.js         placeholder world data
js/player.js        placeholder player state
js/render.js        camera and canvas rendering
js/main.js          boot, status and frame loop
tests/              seed logic tests
tools/page_check.py static and browser checks
```
