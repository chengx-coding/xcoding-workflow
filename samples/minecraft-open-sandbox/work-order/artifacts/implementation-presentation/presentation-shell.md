---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261101-2045-open-sandbox-xc-2"
node_id: "rt_work-order-20261101-2045-open-sandbox-xc-2__dyn-1__presentation-shell"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261101-2045-open-sandbox-xc-2/runtime/orchestration.xml"
---

# Presentation, shell and browser verification implementation

## Changed paths

- `index.html` — playable page shell: HUD, crosshair, hotbar, toast, save indicator, help/pause/craft
  panels, and the full classic-script load order for the new modules.
- `css/style.css` — responsive 16:9 canvas, Minecraft-like dark UI, hotbar slots with swatches and
  counts, overlay panels, crafting rows, toasts, save indicator, unchanged green/red status marker.
- `js/audio.js` — lazy WebAudio synthesis for dig, break, place, jump, land, craft, click, save and
  error; mute/unmute; silent graceful fallback.
- `js/input.js` — keyboard/pointer state, CSS-scaled canvas coordinate mapping, jump edge, wheel,
  context-menu suppression, focus-loss reset.
- `js/render.js` — pre-rendered block textures with variants, time-lerped sky with sun/moon/stars and
  clouds, parallax hills, animated water, torches, crystal glow, light overlay, blocky animated
  avatar, particles, break cracks, target highlight, vignette.
- `js/ui.js` — hotbar DOM, HUD clock/coordinates, help overlay sourced from the same config controls,
  pause menu, crafting list with live cost/eligibility, toasts, save indicator, new-world
  confirmation.
- `js/main.js` — boot/load, fixed-step game loop, camera, interactions, mining/placing, crafting,
  autosave, pause/new-world/save, `window.__sandbox` state surface for the browser check.
- `tools/browser_check.mjs` — dependency-free DevTools-Protocol harness launching headless Chrome,
  driving real key/mouse events, asserting the playable loop and reload persistence, recording
  console errors and network requests, and capturing screenshots.

## Validation

- `node --test "tests/**/*.test.js"` -> 41 tests, 41 pass, 0 fail.
- `python tools/page_check.py` -> `ok=true`; static checks clean; status pixel `[46,204,113]`
  distance 0.0; canvas colour buckets 173 (seed baseline 27).
- `node tools/browser_check.mjs` -> `ok=true` with 16 passing steps: boot, no-network, initial state,
  jump, move right, mine tree, craft planks, place planks, help overlay, pause/save, reload
  persistence, day/night light, responsive mapping, audio mute, new world, console clean.
  `consoleErrors=[]`, `remoteRequests=[]`; 30 page requests, all local `file://`.
- Screenshots captured at `tmp/final-shots/01-boot-day.png`, `02-pause.png`, `03-day.png`,
  `04-night.png`.
- Six consecutive full harness runs passed after the camera-settle and starter-tree fixes; the only
  earlier failures were harness targeting problems (moving camera and a natural tree out of reach),
  not product defects.

## Capability coverage in this unit

- C1 `file://` offline run: boot + no-network + page_check static scan.
- C3 movement/jump/collision: real keyboard events plus the physics suite.
- C4 mining: real mouse hold on a real trunk, block removed, wood collected.
- C5 inventory/hotbar: counts, selection, `Digit4` selection; DOM assertion in harness.
- C6 placement: real right-click placed planks and consumed one.
- C7 persistence: pause-menu save, page reload, world edit + inventory + player position restored.
- C8 controls documentation: in-game help shows 10 control rows; README follows in the docs node.
- C10 day/night and light: `setTimeOfDay` day/night screenshots; brightness 99.2 -> 21.6.
- C12 audio: first gesture unlocks; mute/unmute toasts verified.
- C13 pause/save/new world: pause menu, save, double-confirm new world all exercised.
- C14 presentation: screenshots show textures, trees, water, avatar animation frame, HUD, hotbar.
- C15 responsive mapping: canvas stays within its design width and tile mapping remains inside it at
  1280x720.

## Convention accounting

- English UI and comments; UTF-8/LF; seed UMD/two-space style retained.
- No external library, font, image, audio file or network request; the page check reports an empty
  problem list and the browser check records zero remote requests.
- Seed tests unchanged and passing; new test files are additive.
- Temporary screenshots/process files live under the work order `tmp/`; no project commit created.
- Existing IDs `game`, `hud`, `hotbar`, `status` preserved for the seed page check.

## Residual risk

- The harness uses two explicit automation affordances (`tileToClient`, `setTimeOfDay`) that are not
  player input; they only make the real-input test deterministic and do not alter gameplay.
- Headless audio is muted by the browser; the mute toggles are verified through their UI feedback,
  not by listening to output.
- The browser check uses a fresh temporary Chrome profile, so `localStorage` persistence is proven
  across reloads within one profile rather than across separate browser launches. The pause menu
  reports the persistent-storage state.
- Extreme window sizes below 620 px hide the long HUD hint by design; the hotbar and canvas remain
  usable.
