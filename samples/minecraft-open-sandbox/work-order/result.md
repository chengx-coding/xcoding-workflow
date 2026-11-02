---
schema_version: 1
document_kind: work-order-result
content_language: "en"
work_order_id: "20261102-1550-open-sandbox-xc-047"
feature_ids: []
orchestration:
  main_tree_ref: ".xcoding/work-orders/20261102-1550-open-sandbox-xc-047/runtime/orchestration.xml"
---

# Result - Emberdeep, a playable offline 2D Minecraft-inspired sandbox

## Outcome

Completed. The repository now contains **Emberdeep**: a playable, offline 2D side-view sandbox
inspired by Minecraft. Opening `index.html` directly from the file system boots the game with no
build step, no package manager, no external library, font, image, audio file or network request. The
world can be explored, mined and built in, materials can be crafted into better tools, a small
day/night survival layer gives night a purpose, an eight-stage journey ends at a placeable Ember
Beacon, and the world, inventory, journey and clock persist across reloads through the title
screen's Continue flow. The controls are documented in `README.md` and in the in-game controls panel.

## What was delivered

- `index.html`, `css/style.css`, and 15 classic script modules under `js/`, all dependent only on the
  browser and each other; every module is also requireable by `node --test` (UMD pattern from the
  seed).
- A deterministic 360 x 140-tile world with a flat spawn meadow, rolling hills, oak forest, sand
  patches, two-octave caves, and coal/iron/ember veins banded by depth; a run-length world codec.
- Real-time block interaction: hold-to-mine with reach, exposure and tool-tier rules; right-click
  placement with support rules; drops and stacking in a 36-slot inventory and 9-slot hotbar.
- Crafting with hand, workbench-proximity and furnace-proximity stations: 15 recipes covering the
  wood, stone and iron tiers plus refining and the Ember Beacon.
- Torch lighting and a day/night cycle; night-only hollows in darkness; health, damage, death and
  respawn; a HUD journey tracker with eight persistent stages.
- A minimap, coordinates, depth label, clock and save indicator for orientation; title, pause,
  inventory/crafting, help, death and victory screens; procedural WebAudio effects and mute.
- `README.md` with the product description, every control, systems, saving behaviour and the two
  project checks; `tools/browser_check.js`, a dependency-free DevTools-protocol harness used as
  browser evidence.

## Goal acceptance conditions and evidence

| # | Acceptance condition | Evidence |
| --- | --- | --- |
| 1 | Runs offline from `file://` with no build step, external reference or network | `python tools/page_check.py` passes its static scan (no external reference, every asset local) and boots the page in headless Chrome; the browser harness loads the same file URL and reports no console errors. |
| 2 | Playable first contact with a first-run affordance | Browser check: first-run title overlay, `Enter world` primary action, saved/no-save summary, three control cards; a real pointer click enters play. Screenshot `01-title-first-run.png`. |
| 3 | Defining Minecraft-like loop and progression depth | Implemented gather -> craft -> station -> tier gate -> deeper ore -> refine -> beacon chain (eight stages, four material tiers). Unit tests prove stage ordering, recipe station rules, tier gating and the beacon chain; browser check proves crafting deltas and night pressure. Analysis and solution record the reference dispositions. |
| 4 | Navigable, legible world | 360-tile world with minimap, coordinates, depth label and compass letters; hills, forest, caves and depth-banded ores; minimap sampling tests and HUD captures. |
| 5 | Real pointer interaction truth | Browser check: 10/10 mining trials through `Input.dispatchMouseEvent` press/hold/release, holds 350-364 ms (>= 90 ms), each verified as a block change; `element.click()` negative control leaves the block unchanged (`2 -> 2`). Raw JSON at `artifacts/verify-browser/browser-check.json`. |
| 6 | Visual and audio direction beyond functional UI | Procedural pixel textures, parallax sky, sun/moon/stars/clouds, day/night and torch lighting, particles, vignette; eight captured states including night and an underground torch chamber; procedural WebAudio with mute. |
| 7 | Progress saved and shown consistently | Save/reload/continue browser proof: pause -> Save now -> reload -> Continue summary (Day 1, 10 blocks mined, 0m 06s) -> world hole, placed block and grass count restored; the in-game indicator reports the same save state. Versioned save with corrupt/quota handling and unit tests. |
| 8 | Controls documented | `README.md` control table and in-game controls panel/pause entry; both list the same inputs. |
| 9 | Quality bar: project checks pass, seed tests unchanged, extra automated coverage | `node --test` 80/80 pass across 10 files; `tools/page_check.py` ok; the seed test file is unchanged; browser harness 13/13 checks true. |
| 10 | No scope narrowing | The accepted capability matrix C1-C19 is implemented and verified; no product-prompt capability was dropped. Non-goals (multiplayer, NPCs/villages, redstone, enchanting, dimensions, bosses, hunger/farming, durability, fluid simulation, creative flight) are recorded in `analysis.md` with rationale and impact as analysis decisions, not goal-authored exclusions. |

## Verification evidence

```console
node --test "tests/**/*.test.js"
# 80 tests, 80 pass, 0 fail, 177.8 ms

python tools/page_check.py
# ok=true; static problems=[]; ready marker [46,204,113] distance 0.0; 148 canvas colour buckets

node tools/browser_check.js --profile <workbench>/tmp/chrome-verify \
  --shots <workbench>/artifacts/screens --out <workbench>/artifacts/verify-browser/browser-check.json
# exit 0; ok=true; 13/13 checks; 10/10 pointer mining at 350-364 ms; no console errors
```

Supporting records:

- `artifacts/impl-foundation/record.md`, `artifacts/impl-gameplay/record.md`,
  `artifacts/impl-experience/record.md` - implementation evidence, changed paths and risks.
- `artifacts/verify-automated/record.md` - command outcomes, per-file assertion coverage and gaps.
- `artifacts/verify-browser/record.md` - pointer trials, persistence sequence, capability mapping,
  gaps.
- `artifacts/screens/` - title, day, pause, continue, restored, night, underground torch and
  inventory captures; `09-page-check.png` from the page check.
- `artifacts/browser-check.json` and `artifacts/verify-browser/browser-check.json` - raw harness
  results.

## Report disposition

Report: not required - work_order.requires_report=false, work_order.report_skip_reason=user_waived; report_path=none; manifest_path=none; workbench=.xcoding/work-orders/20261102-1550-open-sandbox-xc-047.

## Capability and scope disposition

Every `must` and `should` capability in the accepted matrix (C1-C19) is delivered and has evidence.
The deliberate simplifications - no hunger/farming, no durability, no fluids, no multiplayer/NPCs/
redstone/dimensions/bosses, no creative flight, desktop mouse and keyboard only - are recorded in
`analysis.md` with user value and impact; none of them removes a capability promised by the product
prompt. The three material tiers, the station-gated crafting, the depth-banded ore access and the
beacon goal give the loop the depth the goal required, so the result is not a gather-only demo.

## Residual risks and gaps

- Audio quality is human-judged; the headless run is muted and only the mute/unmute mechanism and
  procedural generation are verified.
- The full beacon/victory playthrough is covered by progression unit tests and the placement path,
  but not by a single browser-driven end-to-end playthrough; that would require many minutes of real
  mining in the harness.
- Hollow contact damage, death and respawn are unit-tested; the browser run proves spawning only.
- The CDP harness uses a test-only `window.__game.test` surface for state reads and screenshot
  staging; the interaction, placement and save proofs use real dispatched input.
- No project Git commit was created, per the project bridge; the enclosing repository owns the
  sample commit.
