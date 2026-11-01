---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-1819-mc-2d-sandbox"
node_id: "rt_work_order-20261030-1819-mc-2d-sandbox__dyn-1__repair-feedback"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Repair — mining break-progress feedback (review D2)

## Scope

Closes the review's medium finding D2: mining removed a block instantly with no hold/progress state and
no character/tool animation. The repair adds a short break-progress model, a growing crack overlay, a
pickaxe swing and a live probe state, while routing refusals through the existing interaction rules.

## Evidence

### Changed paths

| Path | Change |
| --- | --- |
| `js/mining.js` | New UMD break-progress state machine: `createMining`, `start`, `advance` (0–1, clamped delta), `cancel`, `isActive`, `progressOf`, `describe`; 0.22 s default |
| `js/interaction.js` | `validateMine()` validates a target without changing the world (bounds, sealed floor, air, reach), and `mineBlock` now reuses it |
| `js/main.js` | A left press starts a break instead of removing the block; the loop advances it and completes through `Interaction.mineBlock`; moving off the tile or pausing cancels it; the probe snapshot exposes `mining`; render state carries it |
| `js/render.js` | Growing crack overlay with dark + highlight strokes, a dust-darkening fill, and a pickaxe swing with a motion arc and outlined head |
| `index.html` | Loads `js/mining.js` before `main.js` |
| `tests/mining.test.js` | 8 state-machine tests (start, advance, complete, clamp, invalid delta, cancel, describe, invalid tiles) |
| `tests/interaction.test.js` | `validateMine` rules and read-only behaviour |
| `tests/render.test.js` | Cracks grow with progress and the pickaxe is drawn; nothing is drawn when idle |
| `tools/journey_check.js` | New held-mining journey: hold the button, assert live progress, capture a mid-break frame, release, assert removal and toast |
| `README.md` | Describes the crack meter and pickaxe swing |

### Commands and outcomes

```console
node --test "tests/**/*.test.js"
# tests 120, pass 120, fail 0

python tools/page_check.py
# ok true, static clean, marker distance 0.0, 251 canvas buckets

node tools/journey_check.js --out <workbench>/tmp/journeys
# ok true, checks 68, failed []
```

New checks (all pass):

- `mining: a held break exposes a live progress state` — `{active: true, progress: 0 < p < 1, tile}`
  after a 95 ms hold.
- `mining: the held break completes and removes the block` — the dirt tile becomes air and the dirt
  count increments.
- `mining: the break is confirmed by a toast`.
- `mining-progress.png` (SHA-256 `0E830D782CBCEE87A6A7DBA2737AF75BDA1E38E7BBDB08186E209E3A3B1F58D9`)
  shows the target tile with a dark crack network outlined in light and the player swinging an outlined
  pickaxe with a motion arc; a crop inspection confirms both read clearly.

### Finding closure

| Finding | Closure |
| --- | --- |
| D2 medium — instant break, no hold/progress or tool animation | Closed: a live progress state exists and is exposed, cracks grow with it, the character swings a pickaxe, refusals still apply at validation time, and the browser probe proves the mid-break state and completion |

Behaviour notes: a quick click still breaks the block after the short animation (the progress continues
after release), moving the pointer off the tile cancels the break, pausing cancels it, and a bedrock or
out-of-reach target is refused immediately without starting progress.

### Convention accounting

English, UTF-8/LF, two-space UMD style, no third-party or network assets, Node-loadable modules and
the status marker contract preserved; no commit created; declared checks re-run.

## Findings

- Break progress is a small, testable state machine rather than a timing hack inside the loop.
- The interaction rule remains the single source of truth: the animation only runs for a legal target
  and completes through `mineBlock`.
- No regression: prior journey checks (placement, refusals, pause, reload, day/night, boundary,
  minimap prerequisite, 1280) still pass.

## Conclusion

D2 is closed with machine-checkable tests and a browser-proven mid-break frame. 120/120 tests,
page check green, 68/68 journey checks.
