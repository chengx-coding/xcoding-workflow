---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-0000-minecraft-sandbox"
node_id: "rt_work-order-20261030-0000-minecraft-sandbox__dyn-1__verify-functional"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261030-0000-minecraft-sandbox\\runtime\\orchestration.xml"
---

# Verification — functional behaviour

## Commands and outcomes

```console
node --test "tests/**/*.test.js"
```

`tests 124`, `pass 124`, `fail 0`, `cancelled 0`, `skipped 0` (log:
`tmp/verify-functional-tests.log`).

```console
python tools/page_check.py --screenshot <workbench>/tmp/verify-functional-pagecheck.png
```

Static checks `ok`; status-marker pixel `[46, 204, 113]` at distance `0.0`; canvas colour buckets
`200` (pass); viewport 960x600 (log: `tmp/verify-functional-pagecheck.log`).

Suite composition: `world.test.js` 6 (the untouched seed tests), `rng.test.js` 10,
`generation.test.js` 10, `player.test.js` 13, `camera.test.js` 8, `interaction.test.js` 20,
`storage.test.js` 11, `daynight.test.js` 9, `ui.test.js` 10, `audio.test.js` 8, `render.test.js` 7,
`shell.test.js` 12.

## Capability evidence map

| Capability | Evidence | Result |
| --- | --- | --- |
| M1 Seeded terrain with grass/dirt/stone and variety | generation tests: identical seed, differing seeds, material counts, caves, trees, bedrock, spawn; screenshots | Proven |
| M2 Gravity, movement, jump, collision | player tests: landing, fast-fall no tunnelling, wall stop, ground-only jump, no double jump, ceiling, bounds; browser snapshot settles at surface 40.9999 | Proven |
| M3 Mining within reach with feedback | interaction tests: refine checks, mining adds stock; browser mined leaf block (stock 12 -> 13); crack stages in render unit tests; visual review | Proven (static feedback checked by review) |
| M4 Placement in empty adjacent cell, never inside player | interaction tests: target selection, player/occupied/floating/reach/stock refusals, successful placement spends stock; browser placement succeeded (grass 24 -> 23) | Proven |
| M5 Hotbar >= 4 types, number keys, visible selection | interaction tests: number mapping, selection wrap, hotbar model; shell test: nine slots in order; screenshots show the selected ring | Proven |
| M6 Camera follows and stays in bounds | camera tests: centre, all-edge clamps, smooth follow, bound guard | Proven |
| M7 localStorage save/restore | storage tests: round-trip, corrupt/version/missing handling, unavailable backend, settings; browser reload restored edited cells and counts | Proven |
| M8 Offline page, no network, status marker | page check static + runtime pass; shell test scans HTML/CSS/JS for network references | Proven |
| M9 Clean code and controls note | shell test checks README sections and commands; module per-concern layout; independent review | Proven (review stage confirms) |
| M10 >= 52 tests including seed tests | 124 tests pass; seed file unchanged with its 6 tests | Proven |
| M11 Nine slots with per-block counts | hotbar model tests, shell slot-order test, screenshots with counts | Proven |
| M12 Numeric seed entry | rng and ui parsing tests; browser `seed('777')` rebuilt the world and showed the new seed | Proven |
| M13 Day/night | daynight tests; browser day and night screenshots; HUD phase label | Proven |
| M14 Pause | ui key tests; browser pause overlay opened and resume restored; screenshots | Proven |
| M15 Procedural audio and mute | audio tests (envelope, muted suppression, resume, failure); mute button hookup; no headless audio output | Proven at behaviour level; audible output not verifiable headless |
| M16 Reduced motion | ui/shell tests; browser emulated reduce query matched and the page still rendered | Proven |
| M17 Wheel selection | interaction cycle tests both directions | Proven at model level; wheel pointer event not exercised headless |
| M18 1280-wide scaling | shell CSS assertion; browser measured app and canvas at 1280px | Proven |
| M19 Coordinates | ui formatting tests; screenshot HUD position/depth | Proven |
| M20 Eighth hotbar block | hotbar model asserts slot 8 is cobblestone; shell asserts markup order | Proven |
| S1 Hover outline, crack stages, particles | render helper tests (crack stages, variants, depth shade); screenshots show rendered world; hover/crack are pointer-driven and covered by review | Partially proven by automation; visual review covers presentation |
| S2 Distinct procedural sounds | audio tests: distinct sound specs, gain envelopes, mute suppression | Proven at behaviour level |
| S3 Parallax, textured tiles, depth shading, caves, trees | render tests; day/night screenshots show layered sky, hills, textured tiles, cave darkness, trees | Proven visually (see review) |
| S4 Help panel, toasts, pause overlay, hover info | ui tests; shell test surfaces; help and pause screenshots | Proven |
| S5 In-page controls note | ui help list test (nine controls); hint bar and help screenshots | Proven |

## Prior-inventory evidence map

| Prior item | Disposition | Evidence | Result |
| --- | --- | --- | --- |
| P1 Per-block counts | improve | interaction counts + mine/place stock changes in browser | Proven |
| P2 52 tests including seed tests | preserve | 124 tests, seed file untouched | Proven |
| P3 Reduced-motion support | improve | CSS query + JS detection + emulated browser run | Proven |
| P4 Wheel selection | preserve | cycle tests both directions | Proven at model level |
| P5 1280-wide scaling | preserve | CSS assertion + 1280px measured layout | Proven |
| P6 Audio/mute | improve | audio tests, mute control, persisted settings | Proven at behaviour level |
| P7 Numeric seed entry | improve | parse tests + browser seed change | Proven |
| P8 Pause | improve | key mapping + browser overlay/resume | Proven |
| P9 Eighth hotbar block | preserve | hotbar model + markup order | Proven |
| P10 Day/night | improve | clock tests + day/night screenshots | Proven |
| P11 Nine-slot hotbar | preserve | markup and model | Proven |
| P12 Coordinates | improve | formatting tests + HUD screenshot | Proven |

## Coverage limits

- Audio is synthesized through WebAudio; headless Chrome has no audible output, so the evidence is
  the audio-graph behaviour, mute suppression and failure-tolerant boot rather than a listening test.
- Wheel selection and the hover/crack overlays depend on pointer input; the model functions are unit
  tested and the visual review inspects them on the rendered page, but no automated pointer event is
  dispatched in headless mode.
- The environment-level checks (night render, pause/help overlays, 1280 scaling, forced reduced
  motion, reload persistence) are executed in the environment verification node; this node records
  the model and page-check evidence and does not double-count them as functional proof.

## Conclusion

Both project commands pass, the whole accepted must/should matrix has named evidence, every prior
inventory item is covered by its recorded preserve/improve disposition, and the remaining evidence
gaps are explicitly limited to headless observability rather than missing implementation.
