---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: 20261102-1145-open-sandbox-xc-044
node_id: rt_work-order-20261102-1145-open-sandbox-xc-044__dyn-1__verify-automated
feature_ids: []
orchestration:
  tree_ref: .xcoding/work-orders/20261102-1145-open-sandbox-xc-044/runtime/orchestration.xml
---

# Verification — automated checks and capability evidence

## Environment

- Windows 10.0.26200 (Microsoft Windows NT 10.0.26200.0), Node v24.13.1, Python 3.12.10,
  Google Chrome 156.0.8078.74 in headless mode.
- Project root is `C:\dev\xcoding-workflow-dev\wf-iterations\open-sample-044\xc\project`; the page
  is opened from `file://`, with no server and no network.

## Commands and outcomes

| Command | Outcome | Evidence |
| --- | --- | --- |
| `node --test "tests/**/*.test.js"` | **PASS** — 79 tests, 79 pass, 0 fail, 0 cancelled, 0 skipped, 199.5 ms | `tmp/verification/node-tests.log` |
| `python tools/page_check.py` | **PASS** — static checks ok (no problems), status marker exact `#2ecc71` (distance 0.0), canvas 125 colour buckets (needs ≥12), viewport 960×600 | `tmp/verification/page-check.log` |
| `python tools/browser_check.py --out artifacts/verification/browser` | **PASS** — `ok=true`; 21/21 in-page steps; two-launch persistence pass; 10 scene screenshots; DNS-blocked offline frame diff 0.0002; night 40.0 darker than day; cave 35.3 darker; backdrop 27.0 % pixels changed; zoom pair 56.8 %; inventory/crafting/guide 70.9–73.3 % | `artifacts/verification/browser/summary.json`, `screenshots/*.png`, `tmp/verification/browser-check.log` |

The seed test suite was not modified or weakened: `tests/world.test.js` still contains its original
six assertions (config contract, flat world, bounds, serialization round-trip, solidity), and the
flat `createWorld` compatibility surface it exercises remains in `js/world.js`.

The seed `tools/page_check.py` was not modified. Its static scan of every page-served file reports
no external reference and no network pattern, which together with the DNS-blocked browser run is the
offline evidence for the "no network access" requirement.

## Capability evidence (accepted matrix)

Every accepted `must` and `should` capability is mapped to executable evidence. "Step" refers to a
step name in the browser self-test (`artifacts/verification/browser/summary.json`).

| Capability | Evidence | Result |
| --- | --- | --- |
| Walk, jump, gravity, collision | `tests/physics.test.js` (8 tests: landing, jump height, wall, ledge step, settle, fall damage, impact); browser steps `keyboard-movement`, `real-pointer-mining-and-placement` | pass |
| Seeded world: surface, caves, ores, trees | `tests/worldgen.test.js` (9 tests: dimensions/spawn, determinism, variety, caves/ores/trees/bedrock, ore depth, definitions, RLE, corrupt payloads); screenshots `day`, minimap | pass |
| Mining: hardness, tool speed, drops, particles | `tests/mining.test.js` (6 tests); browser `mining-produces-drops-and-backdrop`, `real-pointer-mining-and-placement` (real pointer hold, 24 simulated ticks, drop granted) | pass |
| Placement: reach, adjacency, overlap | `tests/placement.test.js` (6 tests); browser `placement-and-undo-redo` and `real-pointer-mining-and-placement` (real right click) | pass |
| Hotbar and inventory | `tests/inventory.test.js` (6 tests); browser `inventory-button-opens-panel`, `crafting-planks-with-click` | pass |
| Crafting converts material into capability | `tests/crafting.test.js` (7 tests); browser `crafting-planks-with-click` (real button click, inventory increased) | pass |
| Tool tiers change mining speed | `tests/mining.test.js` (`wooden`/`stone` pickaxe timing and harvest tiers) | pass |
| Day/night cycle and sky | `tests/time.test.js` (8 tests); browser `time-wait-pulse-and-sky`, `night-is-darker-than-noon` (90 → 21 brightness); screenshot pair (40.0 delta) | pass |
| Skylight and torch light | `tests/lighting.test.js` (5 tests); screenshots `cave` (torch pools, 35.3 darker than day); `render.js` torch glow | pass |
| Torch craftable and placeable | `tests/crafting.test.js`, `tests/lighting.test.js`; scene `night`/`cave` place torches through `bulkSet` edit path | pass |
| Save/load world, player, inventory, time, tasks | `tests/save.test.js` (6 tests); browser persistence: `save-write` then `save-read` in separate Chrome launches restore day 6, player position, placed glass, inventory and mute | pass |
| Storage-failure fallback | `tests/save.test.js` forced write failure → memory adapter, surfaced `error`, still saves/loads | pass |
| First-run affordance | browser `first-run-welcome` (welcome + Play/Guide/New buttons), `welcome-play-click`, `primary-system-buttons` (7 visible buttons), `quest-tracker-visible` (8 tasks, title, hint); screenshot `welcome` | pass |
| Visual-state backdrop (edit/mode/time/view) | browser `mining-produces-drops-and-backdrop` (before/after labels Wood → Air), `placement-and-undo-redo`, `backdrop-mode-toggle`, `zoom-pulse-and-minimap-trail`, `time-wait-pulse-and-sky`; screenshots `backdrop` (27.0 % changed), `zoom1`/`zoom2` (56.8 % changed), `day`/`night` | pass |
| Experience lens (discoverability/visual review/progression) | First-run entry points + quest tracker + hover hints; before/after artifacts; 8-step task chain with rewards; reviewed in `experience-review` node and screenshots | pass |
| Controls documented in product and README | browser `guide-documents-controls` (16 control rows, Mine/Place/Save present); `README.md` controls table | pass |
| Task chain with rewards | `tests/tasks.test.js` (6 tests); browser `quest-reward-and-completion` (first_wood complete, reward torches granted) | pass |
| Minimap with viewport trail | browser `zoom-pulse-and-minimap-trail` (`minimapPrevious` recorded, caption updated); screenshots show map + trail | pass |
| Procedural audio | browser `audio-and-mute` (context available, 12+ effects played after gestures, mute restores) | pass |
| Zoom controls | browser `zoom-pulse-and-minimap-trail` includes a real `WheelEvent`; screenshot pair 56.8 % different | pass |
| Backdrop inspect mode | browser `backdrop-mode-toggle`; screenshot `backdrop` with ghost outlines and mode pulse | pass |
| Custom seed / new world | `tests/worldgen.test.js` seed determinism; browser `new-world-from-seed` (seed 424242 adopted, progress reset) | pass |
| Undo/redo of edits | `tests/backdrop.test.js` (8 tests); browser `placement-and-undo-redo` (block removed then restored) | pass |

Deferred capabilities (mobs/combat/hunger, critters, redstone, dimensions, stations/grid, fluids,
touch input) are recorded deferrals in `solution.md` with reason, impact and re-entry trigger; they
are not gaps in this verification.

## Unexecuted checks and gaps

1. **Save file export/import**: the envelope round-trip is unit-tested and the menu wiring is
   inspected, but a real browser download/upload is not automated in the headless capture path. This
   is a manual-path residual risk, not an unverified save code path.
2. **Audio quality**: only the state path (available, gesture-gated, mute) is machine-checked; the
   synthesized sound itself is not machine-assessable.
3. **Timing metrics under virtual time**: `lastRelightMs`/`lastFrameMs` read 0 in headless virtual
   time; the self-test asserts the metric path and bounded tile count instead of a wall-clock
   threshold. No evidence of a performance regression exists, but no quantitative frame budget was
   measured.
4. **Cross-browser coverage**: all browser evidence is Google Chrome 156. No Firefox/Safari run was
   performed in this environment.
5. **Narrow-viewport visual review**: the 780 px breakpoint (action buttons above hotbar, minimap
   hidden) is implemented and exercised by `page_check` at 960×600, but no screenshot review exists
   below 780 px.
6. **Planned `tests/camera.test.js` was replaced**: zoom/camera live in browser-only `main.js`, so
   zoom is verified by the wheel/button browser steps and paired screenshots rather than a Node
   unit test. The capability is covered; only the planned file name changed.

## Conclusion

All three declared verification layers pass on the final code, the untouched seed checks are green,
every accepted capability maps to executable evidence, and the six recorded gaps are either manual
paths, environment limitations, or recorded deferrals — none is a failing acceptance condition.
