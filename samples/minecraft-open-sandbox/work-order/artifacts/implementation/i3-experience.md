---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: 20261102-1145-open-sandbox-xc-044
node_id: rt_work-order-20261102-1145-open-sandbox-xc-044__dyn-1__i3-experience
feature_ids: []
orchestration:
  tree_ref: .xcoding/work-orders/20261102-1145-open-sandbox-xc-044/runtime/orchestration.xml
---

# I3 implementation record — rendering, UI and experience

## Changed paths

- `index.html` — full product shell: canvas, HUD, action buttons, quest tracker, backdrop
  before/after panel, minimap, hotbar, welcome overlay, inventory/crafting/guide/menu panels,
  toasts, hints, hidden self-test sink, seed `#status` marker, script order.
- `css/style.css` — complete responsive visual system (HUD, panels, hotbar, quests, pulse,
  minimap, overlays, status marker contract, mobile breakpoints).
- `js/render.js` — rewritten renderer: time-driven sky palette, stars, sun/moon, parallax hills,
  clouds, underground backdrop, procedural 3-variant tile textures for every block, cave texture,
  neighbour highlights, skylight/torch lighting overlay, torch glow, backdrop ghosts, hover and
  placement previews, mining cracks, animated player, particles, vignette, minimap with viewport
  trail, item/block icon painter.
- `js/audio.js` — new: lazy WebAudio procedural effects and mute state.
- `js/ui.js` — new: DOM construction and updates (hotbar, inventory, crafting, quests, guide data,
  pulse panel, minimap caption, toasts, hints, panels, welcome, menu, save notes, status marker).
- `js/main.js` — rewritten controller: boot/load/new-game, DPR resize, camera, real input
  (keyboard and pointer), mining/placing loop, time/day, tasks, health/fall damage, undo/redo,
  zoom/wait/mode actions, autosave and on-exit save, export/import, world seeds, API for
  scenes/self-test.
- `js/scenes.js` — deterministic screenshot scenes (`welcome`, `day`, `night`, `backdrop`, `zoom1`,
  `zoom2`, `cave`, `inventory`, `crafting`, `guide`, `menu`, `tower`).
- `js/selftest.js` — 19-step in-browser self-test driven by DOM clicks, real pointer events, real
  keyboard events and explicit simulation ticks; plus two-run save writes/reads.

## Validation

- `python tools/page_check.py` → **ok**: static checks clean, status marker pixel exact green,
  canvas 125 colour buckets (contract requires ≥12). The seed page check was not modified.
- `node --test "tests/**/*.test.js"` → 79/79 pass (unchanged by this slice).
- In-browser self-test (`?selftest=1`, headless Chrome, `--dump-dom`) → **19/19 steps pass**:
  boot + non-blank canvas, first-run welcome, click-to-play, seven primary-system buttons visible,
  quest tracker, inventory panel by click, crafting by click, command mining with backdrop labels,
  placement + undo/redo, **real pointer mining and right-click placement**, **real keyboard
  movement**, backdrop mode toggle, zoom pulse + minimap trail, wait/time pulse + sky change,
  night darker than noon (90 → 21 mean brightness), guide with 16 documented controls, quest
  reward, save payload parse (9,268 bytes) and audio/mute.
- Two-launch persistence (`?selftest=save-write` then `?selftest=save-read` with a shared Chrome
  profile) → both pass: day 6, player position, a placed glass block, inventory counts and the mute
  setting all restore from browser storage.
- Visual review of captured scenes (`welcome`, `day`, `night`, `backdrop`, `cave`, `zoom1`,
  `zoom2`, `inventory`, `crafting`, `guide`) confirmed the before/after pulse, minimap viewport
  trail, torch glow and day/night contrast are actually visible.

## Notes and residual risk

- Lighting is recomputed on every edit; measured `lastRelightMs` is recorded by the API and is
  expected to remain in the low single-digit milliseconds for 18,432 tiles (verified in the
  verification stage).
- The first-run welcome is shown only when no save exists; browser autosave starts immediately, so
  later loads resume directly (as designed).
- The renderer draws only visible tiles; at the largest supported viewport the cost is bounded by
  the visible tile count, not the world size.
- No external asset, network reference, dependency, or Git commit was introduced.
