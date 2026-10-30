---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-0000-minecraft-sandbox"
node_id: "rt_work-order-20261030-0000-minecraft-sandbox__dyn-1__impl-presentation-shell"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261030-0000-minecraft-sandbox\\runtime\\orchestration.xml"
---

# Implementation — presentation, audio and shell

## Scope

Approved implementation unit U5 (and the U5-facing parts of the quality contract): textured canvas
rendering with feedback, procedural audio and mute, the accessible page shell with HUD, nine-slot
hotbar, seed panel, help and pause overlays, 1280-wide scaling, reduced-motion rules, README, and the
remaining shell/ui/audio/render tests. Capabilities M5 (shell side), M8, M9, M12, M14, M15, M16, M18,
M19 and S1-S5.

## Changed paths

- `project/js/render.js` — replaced the flat renderer with pre-rendered textured tile variants,
  day/night sky, sun/moon/stars, drifting clouds, two parallax hill layers, depth shading, dark cave
  interiors, block edge lighting, grass/flower decorations, deterministic hover/crack overlays,
  particles, a blocky player sprite with walk/jump/mine animation, fireflies at night and a subtle
  vignette.
- `project/js/audio.js` (new) — procedural WebAudio sound set (mine, break, place, jump, select,
  deny, save), gain envelopes, gesture-time context creation, resume on suspend, mute and safe
  degradation when audio is unavailable.
- `project/js/ui.js` (new) — key action map (movement, digits, pause, mute, help, respawn), text-entry
  detection, coordinate/depth/count formatting, seed parsing delegation, reduced-motion detection,
  help content and toast text.
- `project/js/main.js` — full boot and loop: world load/restore, seed panel, input wiring (keyboard,
  pointer, wheel, buttons), mining hold and placement, particles, camera, autosave and pagehide save,
  pause freeze/overlay, mute persistence, toasts, HUD/hotbar updates, status marker, reduced-motion
  listener and a small `window.__sandbox` verification surface.
- `project/index.html` — accessible shell: canvas, HUD with seed editor/coordinates/time/depth/target,
  nine hotbar slot buttons, top action buttons, hint bar, toast region, help and pause dialogs, status
  marker, script order.
- `project/css/style.css` — full visual design (brand panel, glass HUD, hotbar swatches per block,
  selected-slot ring, overlays, toasts, focus styles), 1280-wide scaling media query and
  reduced-motion media query.
- `project/README.md` — rewritten to document the game, controls, checks and architecture.
- `project/tests/ui.test.js`, `project/tests/audio.test.js`, `project/tests/render.test.js`,
  `project/tests/shell.test.js` (new).

## Validation

```console
node --test tests/ui.test.js tests/audio.test.js tests/render.test.js tests/shell.test.js
python tools/page_check.py --screenshot <workbench>/tmp/impl-presentation-pagecheck.png
```

Result: 37 focused tests pass (log: `tmp/impl-presentation-tests.log`); page check passes with the
status pixel at distance 0.0 and 202 canvas colour buckets, screenshot
`tmp/impl-presentation-pagecheck.png` (log: `tmp/impl-presentation-pagecheck.log`).

Browser evidence from the CDP harness (`tmp/visual-verify.json`, screenshots in `tmp/`): boots to
`ready` with no console errors or exceptions; day and night renders; pause overlay opens and resumes;
the nine-row help dialog renders; 1280-wide metrics report a 1280px app and canvas; the
reduced-motion media query is honoured; a seed change and world edits survive a reload.

## Convention accounting

- C1 bridge — English, two-space indentation, UMD modules, Node-loadable, no network, `file://`
  friendly: followed. The renderer and main obtain canvas/DOM only inside functions, so requiring
  them under Node stays safe.
- C1 bridge — keep the `#status` marker contract: followed and verified by the page check.
- C1 bridge — keep README accurate: README rewritten to match delivered behaviour and controls.
- C1 bridge — do not weaken tests: seed tests untouched; new suites add coverage.
- C1 bridge — no project commit: followed.
- No C2 signal applies.

## Residual risk

- Rendering is intentionally 2D canvas at a fixed 960x540 backing store and scales by CSS; on very
  high-DPI displays it will look soft rather than crisp. That matches the seed page and the offline
  constraint.
- The audio set is synthesized and deliberately quiet; a future request could add volume control,
  which is not part of the accepted matrix.
- Help and pause overlays trap focus lightly (focus moves to the close/resume button) but do not
  implement a full focus trap; keyboard navigation still reaches the game.
