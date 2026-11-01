---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261101-2045-open-sandbox-xc-2"
node_id: "rt_work-order-20261101-2045-open-sandbox-xc-2__dyn-1__browser-and-regression"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261101-2045-open-sandbox-xc-2/runtime/orchestration.xml"
---

# Verification — interactive browser behaviour, offline and regression

## Commands and outcomes

Environment: Windows, Node v24.13.1, Python 3.12.10, local Chrome; page opened as
`file:///C:/dev/xcoding-workflow-dev/wf-iterations/open-sample/xc/project/index.html`.

1. `python tools/page_check.py --screenshot .../tmp/verify-page-final.png` -> **`ok=true`**;
   static, status-marker and canvas-colour checks all pass.
2. `node tools/browser_check.mjs --screenshots .../tmp/verify-shots` -> **`ok=true`**, 16/16 steps
   passed, `consoleErrors=[]`, `remoteRequests=[]`, 15 page requests all local `file://`.
3. `node --test "tests/**/*.test.js"` (regression after all implementation) -> **41 tests, 41 pass,
   0 fail**.

## Browser steps

| Step | Result | Evidence |
| --- | --- | --- |
| boot | pass | `window.__sandbox.ready`, status `ready`, world 192x96, 8 hotbar slots |
| no-network | pass | 15 requests, 0 `http(s)` requests |
| initial-state | pass | player at (96.5, 62.999999), on ground, seed 1137813947, persistent storage |
| jump | pass | rose 1.813 tiles and landed back on the surface |
| move-right | pass | x 96.5 -> 99.65 with real `KeyD` events |
| mine-tree | pass | held real left mouse over the starter trunk; block became air; wood +1 |
| craft-planks | pass | real `E` then real click on the planks button: wood 1 -> planks 4 |
| place-planks | pass | real right-click placed block id 11 and left 3 planks |
| help-overlay | pass | 10 documented control rows; `Esc` closes it |
| pause-save | pass | pause menu opens, Save now writes `localStorage` |
| reload-persistence | pass | after a real page reload: same seed, player x 99.65, planks 3, placed block id 11 |
| day-night-light | pass | sky 15 -> 4; canvas brightness 106.10 -> 21.37 |
| responsive-mapping | pass | at 1280x720 the canvas stays 960 wide and the tile mapping stays inside it |
| audio-mute | pass | `M` shows "Audio muted." then "Audio on." |
| new-world | pass | double confirmation changes seed 1137813947 -> 3660678589, closes pause, spawns safely |
| console-clean | pass | zero exceptions, zero console errors, final status `ready` |

## Screenshot review

Captured at `tmp/verify-shots/` and reviewed visually:

- `01-boot-day.png` (249,912 bytes) — bright day sky, sun, clouds, parallax hills, layered grass/dirt/
  stone terrain, trees, sand and water, textured blocks, animated avatar, HUD clock, 8-slot hotbar,
  selected slot outline, green status dot.
- `02-pause.png` (117,637 bytes) — centred paused panel with resume/save/controls/new-world, inventory
  summary, seed and world size, dimmed game behind it.
- `03-day.png` (253,451 bytes) — restored world after reload; placed planks visible, planks x3 in the
  hotbar.
- `04-night.png` (192,406 bytes) — dark night sky with stars and moon, darkened terrain, the same
  player and placed block; confirms the time and light change is visible, not only numeric.

## Capability evidence

- **C1** offline: no remote requests, static scan clean, page runs from `file://`.
- **C3** movement/jump/collision: real key events moved and jumped the player and returned to ground.
- **C4** mining: real pointer hold removed a trunk and produced the correct drop.
- **C5** inventory/hotbar: counts, selection, and DOM slot state observed.
- **C6** placement: real right click placed the selected block and decremented the count.
- **C7** persistence: pause save -> page reload restored world edit, inventory and position.
- **C8** controls: help overlay contains all 10 controls; README documents the same list.
- **C10** day/night and light: numeric sky level and measured scene brightness both change.
- **C12** audio: first gesture unlocks audio; mute state has visible feedback.
- **C13** pause/save/new world: all three interactions exercised.
- **C14** presentation: screenshot review confirms the visual quality claims.
- **C15** responsive mapping: second viewport verified.

## Gaps and observations

- Headless Chrome is launched with `--mute-audio`; audio is verified through its state/feedback, not by
  listening. The WebAudio path is exercised without errors.
- Storage persistence is proven across reloads inside one temporary Chrome profile, which is the
  `file://` origin the player uses; cross-profile persistence is a browser policy, not game logic.
- No numeric FPS budget was set by the request; the browser run completes its interactions without
  timing failure, and no frame-rate assertion is recorded as a pass.
- The browser harness uses `tileToClient` for deterministic real-input coordinates and `setTimeOfDay`
  for the day/night capture; neither changes gameplay.

## Conclusion

The interactive verification passes every required capability, the offline contract, the reload
persistence requirement and the visual review. Combined with the focused unit/static node, the
accepted capability matrix has executable evidence for every must and accepted should capability; no
blocking gap remains.
