---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-1819-mc-2d-sandbox"
node_id: "rt_work-order-20261030-1819-mc-2d-sandbox__dyn-1__impl-experience"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Implementation record — experience and presentation (IU2)

## Scope

Implemented the accepted solution's experience/presentation unit: page shell, styling, rendering,
UI model, audio, main wiring, the automated browser journey probe, the README, and the remaining
tests. It completes the page on top of IU1's simulation modules.

## Evidence

### Changed paths

| Path | Bytes | Purpose |
| --- | --- | --- |
| `index.html` | 3948 | Canvas shell, top bar (brand, coordinates, clock, seed, pause/mute, seed form), HUD, nine-slot hotbar, toast layer, pause overlay, controls hint line, all module scripts, `#status` marker preserved |
| `css/style.css` | 11576 | Visual system: glass top bar and palette, amber accent, warm/cool hierarchy, 1280-wide responsive layout, reduced-motion media query, marker colours |
| `js/render.js` | 19151 | Canvas presentation: time-driven sky, sun/moon, stars, clouds, camera-anchored parallax hills, textured block faces, hover highlight, particles, player sprite, night darkening with a player light, vignette, cave backdrops |
| `js/ui.js` | 2807 | Pure presentation model: hotbar, selection maths, coordinates, clock phases, target text, toast lifetime |
| `js/audio.js` | 3205 | Lazy WebAudio cue generator with mute and silent failure |
| `js/main.js` | 23460 | Boot/restore, input, loop, camera, hotbar, HUD, toasts, pause, seed form, mute, saving, error status, `window.__sandbox` probe surface, DPR-aware canvas |
| `tools/journey_check.js` | 27171 | Automated CDP journey probe with screenshots and JSON report |
| `README.md` | 4880 | What was built, how to run, controls, mechanics, architecture, verification commands |
| `tests/render.test.js` | 8242 | 11 rendering and visible-state tests |
| `tests/ui.test.js` | 2403 | 6 presentation-model tests |
| `tests/audio.test.js` | 2993 | 6 audio tests |

### Commands and outcomes

```console
node --test "tests/**/*.test.js"
# tests 104, pass 104, fail 0 (6 unchanged seed tests + 98 added)

python tools/page_check.py --screenshot <workbench>/tmp/screenshot-960x600.png
# static ok, status marker rgb(46,204,113) at distance 0.0, canvas colour buckets 251, ok true

node tools/journey_check.js --out <workbench>/tmp/journeys
# 52 checks, 0 failed, ok true
```

### Executed journeys and visible states

The journey probe drives the real page in headless Chrome at 960x600 and records the before/after
state of every journey, with screenshots under `<workbench>/tmp/journeys/`:

| Journey | Executed evidence |
| --- | --- |
| Boot, palette, canvas | status `ready`, 9 slots, selection ring on slot 1, ≥12 canvas colour buckets, hint line contains move/mine/build, no horizontal overflow |
| Hotbar keys/wheel | key 5 selects slot 5; wheel advances; exactly one slot has the selected class; wrapping returns to slot 1 |
| Mine | block at (13,41) changes from solid to air; inventory grass 16→17; visible `+1 grass` toast; the tile pixel changes by RGB distance > 40 and becomes background-blue at the same anchor |
| Place | planks occupy (14,40), count 12→11, `Placed planks` toast, the new block's pixel is visibly drawn |
| Refuse occupied | (14,40) pixel unchanged (<6 distance); `That spot is not empty` visible in a toast element |
| Refuse player | right-click on the player cell leaves it air and shows `You are standing there` |
| Refuse empty palette | leaves count 0 → `No leaves left` and the cell stays air |
| Pause | overlay covers >800x400 with backdrop blur; clock frozen for 700 ms; resume hides it and motion resumes |
| Reload persistence | mined and placed blocks, counts and player position survive a real page reload; restore toast visible |
| Corrupt save | corrupt payload injected before the next document's scripts; page stays `ready`, regenerates a fresh world, and shows the unreadable-save notice |
| Day/night | two 960x600 screenshots with materially different sky pixels, HUD clock `12:00 day` vs `00:01 night`, and a foreground block still drawn and readable at night |
| Boundary | camera clamps to x=0 at the left edge and x=128*32−960 at the right edge; the player stays inside |
| Error status | a dispatched runtime error turns `#status` red (`rgb(231,76,60)`); reload recovers `ready` |
| 1280-wide | layout and canvas grow to 1280, no horizontal overflow, hotbar inside the viewport, 1280x800 screenshot captured |

### Visual iteration

- First render: correct but visually flat; the spawn plateau filled most of the frame and the palette
  and background had no depth.
- Iteration 1: moved the deterministic tree line closer to spawn, added flowers and stone details to
  the tile faces, and corrected the coordinate rounding.
- Iteration 2: the parallax hills were anchored to the camera, so they were invisible behind terrain;
  they were re-anchored to the world's base surface line with reduced size and opacity so they read as
  distant ridges.
- Iteration 3: cave air was showing the sky gradient (pale rectangles underground); air below the
  generated surface now paints a dark cave backdrop, while a mined surface block still reveals the sky
  at its own anchor (verified by the mine journey).
- The final 960x600 frame (`tmp/journeys/final-960x600.png`) shows the top bar, HUD, sun and layered
  hills, textured terrain, a tree, the player, placed planks/brick, all nine palette slots with counts
  and the controls line.

### Convention accounting (bridge rules)

| Rule | Status |
| --- | --- |
| English UI text, code and comments | followed |
| UTF-8 with LF | followed |
| No project Git commit | followed; no commit created |
| No build step, `file://` | followed: static scripts only, no modules/bundler/server |
| No third-party libraries, CDNs, fonts or network requests | followed: system fonts, no external URLs, page check static scan clean |
| Two-space JavaScript and the existing UMD module style | followed |
| Node-loadable logic modules | followed: render/ui/audio are exercised by Node tests; DOM wiring stays in `main.js` |
| Keep the `#status` marker contract and the existing layout | followed: ids preserved, marker colours unchanged, red error state proven |
| Keep the seed tests | followed: `tests/world.test.js` untouched and passing |
| Declared verification commands | `node --test`, `python tools/page_check.py` and the new journey probe executed |

### Residual risks

- The probe surface (`window.__sandbox`) is intentionally thin but is a public object; it exposes
  read state and a few commands for automation and is documented as such in the README.
- Pixel probes read stable anchors with tolerance; they are sensitive to major palette changes, so
  future visual work should re-run the probe.
- The cave backdrop depends on the generated surface; a world loaded from a save without the original
  surface still resolves it deterministically from the seed.
- Audio requires a first user gesture and fails silent; headless checks mute audio.
- The journey probe needs Node 22+ and a local Chrome; the project check itself does not depend on it.

## Findings

- The page is complete against the accepted matrix: every requested capability is exercised, the
  palette, counts, seed form, pause, mute, day/night, reduced motion and 1280 scaling are present.
- The visible-state obligations are satisfied with executed evidence rather than inspection: the mined
  tile's replacement background, the refusal toasts over an unchanged world, the pause occlusion, and
  two materially different day/night frames.
- No external resource is referenced; the page check's static scan and the source inventory agree.

## Conclusion

IU2 is complete. The final verification stage (`verify-tests`, `verify-page`, `verify-journeys`) and
the independent visual review will re-run these commands and map the results to the capability
matrix.
