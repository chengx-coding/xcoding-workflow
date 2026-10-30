---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-0000-minecraft-sandbox"
node_id: "rt_work-order-20261030-0000-minecraft-sandbox__dyn-1__verify-environment"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261030-0000-minecraft-sandbox\\runtime\\orchestration.xml"
---

# Verification — environment, scaling, input and persistence

## Method

The page was loaded from its real `file://` path in headless Chrome through a temporary
DevTools-protocol harness under the workbench (`tmp/visual_verify.mjs`), not through a development
server. The harness drove real input events, changed the emulated viewport and media features, and
captured PNG screenshots into `tmp/`. Raw results: `tmp/visual-verify.json` and
`tmp/visual-verify-run.log`.

## Evidence

| Check | Observed | Result |
| --- | --- | --- |
| Boot from `file://` | status `ready`, `window.__sandbox` present, initial snapshot seed 20261030, player settled at `y 40.9999`, `onGround true` | Pass |
| Console / page exceptions | `errors 0`, `console 0` entries | Pass |
| Day render | `tmp/day-960.png` | Pass |
| Night render | time set to 0.782; `tmp/night-960.png` shows dark sky, stars, moon, fireflies, night HUD label | Pass |
| HUD hover readout | real pointer move over a leaf block -> `#hud-target` text `Leaves` | Pass |
| Real mouse mining | pointer press held 800 ms over `(64, 40)` leaf -> block becomes `0`, leaves stock `12 -> 13` | Pass |
| Real keyboard movement | `A` held 350 ms with the player grounded -> x delta `-1.150` tiles | Pass |
| Real keyboard jump | `Space` on the ground -> y delta `1.769` tiles upward before landing | Pass |
| Number-key selection | `3` -> `selected 2` | Pass |
| Wheel selection | wheel delta +120 over the canvas -> `selected 3`, `tmp/selected-slot.png` shows the selected slot | Pass |
| Pause | pause button -> `paused true`, overlay visible, `tmp/pause-960.png`; resume -> `paused false` | Pass |
| Help | help button -> 10 control rows rendered, `tmp/help-960.png` | Pass |
| Mine + place + reload | mined leaf and placed sand block persisted: `blockAt` returns `0` and `6` after reload, counts `{1:24,2:32,3:24,4:16,5:14,6:15,7:20,8:16,9:8}` | Pass |
| Seed change + reload | `seed('777')` -> HUD 777, screenshot `tmp/seed-777.png`; reload -> seed `777` | Pass |
| `localStorage` present | save key exists after save | Pass |
| 1280-wide scaling | emulated 1280x800 looks up the 1280 media query: app width `1280`, canvas width `1280`, `tmp/wide-1280.png` | Pass |
| Forced reduced motion | `matchMedia('(prefers-reduced-motion: reduce)').matches` true after reload, page still ready, `tmp/reduced-960.png` | Pass |

## Capability coverage added here

- M2 proven through real keyboard jump and movement, not only unit tests.
- M3/M4 proven through a real pointer press over the canvas, not only model calls.
- M5/M17 proven through real number-key and wheel input.
- M7 proven by a reload of the real `file://` page restoring edited cells and counts.
- M12 proven by the seed field path in a live page.
- M13/M14/M16/M18 proven by rendered states.
- M8 proven by `file://` boot with no network and the page check (functional node).
- Prior P3-P8, P10 and P12 are confirmed at browser level by the same observations.

## Coverage limits

- Headless Chrome produces no audible output, so audio remains verified at the graph/model level.
- Hover and crack overlays are rendered from pointer state; the hover readout and selected state were
  inspected, and the static visuals are covered by the independent visual review.
- Long-session performance, touch input and non-Chrome browsers are outside this work order's
  declared environment.

## Conclusion

The page works from `file://` with real input, renders day and night, pauses and resumes, restores
edits and settings, scales at 1280 pixels, honours reduced motion, and reports no runtime errors. No
accepted capability is unproven at this stage except listening to audio, which is a headless
environment limit rather than a missing implementation.
