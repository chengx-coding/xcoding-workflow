---
schema_version: 1
document_kind: node-artifact
content_language: "en"
audience: "internal"
work_order_id: "20261102-1550-open-sandbox-xc-047"
node_id: "rt_work-order-20261102-1550-open-sandbox-xc-047__dyn-1__impl-experience"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261102-1550-open-sandbox-xc-047/runtime/orchestration.xml"
---

# Implementation record - experience (render, UI, audio, input, shell, docs)

## Scope

The accepted experience unit from `solution.md`: the playable presentation around the simulation -
procedural pixel rendering, the HUD and menus, real pointer and keyboard input, the fixed-step boot
loop with save orchestration, the page shell and stylesheet, the controls documentation, and the
dependency-free browser evidence harness.

## Changed paths

| Path | Change |
| --- | --- |
| `js/render.js` | Rewritten: procedural 24x24 block textures with variants, sky gradients by time, sun/moon/stars/clouds, parallax mountains, cave backdrop, dug-hole back walls, day/night lighting composite, torch/beacon glow, player and hollow sprites, held item, selection ghost, mining cracks, particles, vignette and fog. |
| `js/audio.js` | New: WebAudio-only effects for mine/break/place/pickup/craft/hurt/death/quest/night/beacon/UI, mute persistence, safe unlock on gesture, no audio files. |
| `js/ui.js` | New: HUD (journey tracker, day/time, coordinates/depth, minimap, hearts, save state), hotbar with icons and counts, title/continue screen, inventory + crafting panel with station reasons, pause menu (save, controls, mute, new world confirmation, quit), help panel, death and victory screens, toasts, hints. |
| `js/input.js` | New: keyboard state, real pointer-to-world mapping from `getBoundingClientRect`, press/hold mining, right-button placement, hotbar keys and wheel, Escape/E/H/M routing, pointer capture and context-menu suppression. |
| `js/main.js` | Rewritten: save-aware boot, fixed-step loop, clock/day-night, mining/placement/attack resolution, tool reach and exposure checks, camera follow, light refresh policy, autosave and manual save, progression events, death/victory flow, hollow pressure, new/continue world flow, `window.__game` state and test hooks. |
| `index.html` | Rewritten shell: required ids `game`, `status`, `hud`, `hotbar` preserved, all classic scripts in dependency order, page metadata. |
| `css/style.css` | Rewritten: pixel-game art direction (slate/gold/ember palette), full-viewport frame, HUD panels, minimap, hearts, hotbar bevels, inventory/recipe UI, menus, toasts, hints, screen-state transitions, reduced-width layout. |
| `README.md` | Rewritten as product documentation: how to start, every control, systems, saving behaviour, goal, checks and layout. No internal workflow paths. |
| `tools/browser_check.js` | New dependency-free Node/DevTools-protocol harness (details in validation). |

## Validation

```console
node --test "tests/**/*.test.js"        # 80 tests, 80 pass, 0 fail
python tools/page_check.py              # static ok, status marker ok, 129 colour buckets, canvas non-blank
node tools/browser_check.js ...         # all 13 checks true, no console errors
```

Browser evidence produced by `tools/browser_check.js` (raw JSON and screenshots in
`.xcoding/work-orders/20261102-1550-open-sandbox-xc-047/artifacts/`):

- **First run** - fresh Chrome profile, overlay `data-screen=title`, primary button "Enter world",
  `hasSave=false`, no saved-summary; a real dispatched pointer click on the primary button enters
  `mode=playing`.
- **Pointer interaction truth** - 10 trials, 10/10 blocks changed, each a genuine
  `Input.dispatchMouseEvent` press held 351-363 ms (minimum required 90 ms) at the computed screen
  position of a reachable, exposed surface tile, released, then verified `blockAt == 0`.
- **Negative control** - `document.getElementById('game').click()` leaves the block unchanged
  (`2 -> 2`), so the passing result cannot come from synthetic element activation.
- **Placement** - a real right-button press on a mined tile restores the block and decreases the
  inventory count by exactly one.
- **Persistence** - Escape opens the pause screen, a real click on **Save now** sets
  `hasSave=true`, `status.kind=ok`; `Page.reload` then shows Continue with the saved summary
  (Day 1, 10 blocks mined, 0m 06s played, just now); continuing restores an open hole, the placed
  block and a grass count of 9.
- **Crafting UI wiring** - real clicks on the Planks and Workbench recipe buttons produce the exact
  expected inventory deltas (wood 6 to 5, planks 4 to 0, workbench 1).
- **Night threat** - with the clock set to 0.78, hollows spawn in darkness (`mobCount > 0`,
  `isNight=true`).
- **Visual states** - captured title, day surface, pause, continue title, restored world, night with
  a hollow, underground with torch light, and the inventory/crafting panel.
- **Console** - zero page exceptions, console errors or error-level log entries during the run.

## Convention accounting

- Project bridge: English, UTF-8/LF, classic `file://`-safe scripts, no external dependency, font or
  network request, temporary profiles and reports kept in `tmp/`/`artifacts/`, no project commit,
  seed tests unchanged.
- C1/C2: none beyond the bridge. C3 seed patterns followed (UMD modules, frozen config, `node:test`).
- The page check's contract is preserved exactly: required ids, fixed ready status dot colour, no
  external references, non-blank canvas.

## Residual risk

- The page is designed for a desktop mouse and keyboard; touch input is not a target and is not
  claimed.
- Procedural art is deterministic per block/tile but palette-tuned by hand; a future block should add
  its texture branch in `render.js`.
- The browser harness relies on the installed Chrome and Node 24's global `WebSocket`; both were
  verified in this environment and the harness fails closed with a clear error otherwise.
- The CDP harness uses a test-only `window.__game.test` surface for state reads and for setting
  visual states; the pointer, placement and save proofs use real input dispatch, not that surface.
