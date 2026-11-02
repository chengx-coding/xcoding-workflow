---
schema_version: 1
document_kind: work-order-solution
content_language: en
work_order_id: 20261102-1145-open-sandbox-xc-044
feature_ids: []
orchestration:
  main_tree_ref: .xcoding/work-orders/20261102-1145-open-sandbox-xc-044/runtime/orchestration.xml
---

# Solution — build Cubewood as a modular offline canvas sandbox

## Scope decision

- **Task type:** `create` (new product on a seed shell), no feature baselines.
- **Minimality strength:** none. A create task is judged by fidelity to the request and the accepted
  quality contract, not by the smallest possible delta.
- **Chosen scope:** implement every `must` and the accepted `should` capabilities from
  `analysis.md` in one coherent product, with the reference systems listed under *Deferred* left out
  of this iteration but recorded as reversible should-items.
- **Implementation boundary:** `index.html`, `css/style.css`, `js/**` (new modules plus the seed
  modules they replace), `tests/**` (seed test preserved and extended), `tools/browser_check.py`
  (new), and `README.md`. The seed `tools/page_check.py` is not modified. No build step, no
  dependencies, no network, no project Git commit.
- **User confirmation:** not required. The only narrowing is the reversible deferral list below, and
  no material human-owned decision remains open (`analysis.md`, request-to-goal comparison).

## Accepted capability matrix

Every accepted capability maps to one implementation unit and one verification route. Units:
**I1** world engine, **I2** simulation and progression, **I3** rendering and experience, **I4**
documentation and browser evidence tooling.

| Capability | Unit | Implementation | Verification |
| --- | --- | --- | --- |
| Walk, jump, gravity, collision | I2 | `js/physics.js` swept-AABB, coyote time, jump buffer | `tests/physics.test.js`, browser selftest |
| Seeded world: surface, caves, ores, trees | I1 | `js/rng.js`, `js/noise.js`, `js/world.js` | `tests/worldgen.test.js`, generated-world statistics test |
| Mining: hardness, tool speed, cracks, particles, drops | I2 | `js/mining.js`, particles in I3 | `tests/mining.test.js`, browser selftest |
| Placement: reach, adjacency, no overlap | I2 | `js/placement.js` | `tests/placement.test.js`, browser selftest |
| Hotbar + inventory with counts | I2 | `js/inventory.js`, UI in I3 | `tests/inventory.test.js`, browser click test |
| Crafting: material → capability | I2 | `js/crafting.js` recipes with unlocks | `tests/crafting.test.js`, browser click test |
| Tool tiers changing mining speed | I2 | `js/blocks.js` tool classes + `js/mining.js` | `tests/mining.test.js` |
| Day/night cycle and sky | I1 | `js/time.js` | `tests/time.test.js`, day/night screenshot pair |
| Skylight + torch light | I1 | `js/lighting.js` flood fill | `tests/lighting.test.js`, cave/torch screenshot |
| Torch craftable and placeable | I2 | recipe + light block | `tests/crafting.test.js`, `tests/lighting.test.js` |
| Save/load world, player, inventory, time, tasks | I2 | `js/save.js` versioned envelope + RLE | `tests/save.test.js`, two-run browser persistence |
| Storage-failure fallback | I2 | memory store + export/import + visible warning | `tests/save.test.js`, forced-failure browser check |
| First-run affordance | I3 | welcome overlay, HUD buttons, task tracker, hints in `js/ui.js` | browser selftest clicking DOM, first-run screenshot |
| Visual-state backdrop (edit/mode/time/view) | I2+I3 | `js/backdrop.js` history/pulses, ghosts in renderer, minimap trail | `tests/backdrop.test.js`, paired screenshots, browser selftest |
| Experience lens | I3 | discoverability entry points, before/after review surfaces, task progression | document analysis + visual review node |
| Controls documented | I3+I4 | in-game guide data + `README.md` | static guide check, README read |
| Task chain with rewards | I2+I3 | `js/tasks.js` definitions and tracker UI | `tests/tasks.test.js`, browser selftest |
| Minimap with viewport trail | I3 | minimap renderer | browser screenshot + selftest |
| Procedural audio | I3 | `js/audio.js` WebAudio blips, lazy gesture start, mute | browser selftest state, manual listen |
| Zoom controls | I3 | camera zoom 0.6–2.5× | `tests/camera.test.js`, zoom screenshot pair |
| Backdrop inspect mode | I3 | mode toggle + world ghosts | browser selftest, mode screenshot pair |
| Custom seed / new world | I1+I3 | seed input + regenerate | `tests/worldgen.test.js`, browser selftest |
| Undo/redo of edits | I2 | edit history stack in `js/backdrop.js` | `tests/backdrop.test.js`, browser selftest |

## Deferred reference systems

None of these is forbidden or excluded from the domain; each is a reversible scope decision of this
iteration, recorded so a later work order can pull it back in. Source: the reference (Minecraft) and
the user's "small Minecraft" wording; they are not user-priority requirements.

| Deferred | Reason | Impact now | Re-entry trigger |
| --- | --- | --- | --- |
| Mobs, combat, damage-based health | Survival threat is a large separate system; the request's core is a creative sandbox | No enemies; player has hearts only for fall damage | A survival work order, or user request |
| Hunger/food | Follows from survival scope | No food loop | Same as above |
| Ambient critters | Atmosphere-only; rendering/behaviour budget | World is quiet | Polish work order |
| Redstone/circuits | Simulation and UI complexity far beyond a small sandbox | No automation | A redstone-focused work order |
| Dimensions (Nether) | Extra world layers, generation, travel | One 192×96 world | Exploration work order |
| Furnace/workbench stations, 3×3 grid | Recipe list is more discoverable and click-testable | Crafting is a menu, not a ritual | Crafting-depth work order |
| Water/lava fluid simulation | A fluid engine is its own subsystem | Static terrain | World-dynamics work order |
| Touch/mobile controls | Desktop keyboard/mouse is the assumed input for this build | No touch play | Accessibility work order |

## Implementation plan

1. **I1 world engine** — `js/config.js` (extended constants), `js/blocks.js` (registry: ids, names,
   hardness, tool class, drops, colours, light emission), `js/rng.js` (mulberry32 + string hash),
   `js/noise.js` (value noise with octaves), `js/world.js` (192×96 generation: layered surface with
   biome bands, caves, ore veins, trees; block access; RLE serialization), `js/lighting.js`
   (skylight + block-light flood fill, daylight factor), `js/time.js` (4-minute cycle, phases, sky
   palette). Tests for generation determinism/statistics, serialization, lighting, time.
2. **I2 simulation and progression** — `js/physics.js` (AABB collision, coyote/jump buffer, fall
   damage), `js/mining.js` (progress, hardness, tool multiplier, reach, drops), `js/placement.js`
   (reach/adjacency/overlap rules), `js/inventory.js` (counts, hotbar, add/remove), `js/crafting.js`
   (recipes, unlocks, affordability), `js/tasks.js` (chain definitions, progress, rewards),
   `js/backdrop.js` (edit history, undo/redo, state pulses), `js/save.js` (envelope, storage
   adapter, export/import, failure fallback). Tests for every module.
3. **I3 rendering and experience** — `js/render.js` (sky, parallax, procedural tiles, lighting
   overlay, player, ghosts, particles, break cracks, minimap), `js/audio.js` (procedural blips),
   `js/ui.js` (welcome, HUD buttons, hotbar, inventory/crafting/guide/menu modals, task tracker,
   backdrop pulse, toasts, hints), `js/main.js` (boot, input, camera, loop, save triggers),
   `js/selftest.js` (deterministic scripted interactions for `?selftest=`), `js/scenes.js`
   (`?scene=` demo states for screenshots), `index.html`, `css/style.css`.
4. **I4 documentation and evidence tooling** — `README.md` controls/save/checks; `tools/browser_check.py`
   (stdlib-only: `--dump-dom` self-tests, scene screenshots, paired-pixel before/after assertions,
   two-run persistence); regenerate evidence into the workbench artifacts.

Seed constraints preserved: `index.html` ids `game`, `status`, `hud`, `hotbar`; the `#status` marker
stays a 14×14 fixed bottom-left element turning green when ready and sits above every overlay; no
network reference appears in any page-served file; the canvas renders a varied world on first load.

## Verification strategy

- `node --test "tests/**/*.test.js"` — logic and data contracts (seed tests preserved, new suites
  added).
- `python tools/page_check.py` — untouched seed page/browser contract.
- `python tools/browser_check.py` — real headless Chrome: static network scan, `?selftest=1`
  scripted interactions covering movement/mining/placement/crafting/save/backdrop/first-run DOM
  clicks, scene screenshots (first run, day, night, backdrop mode, zoom pair, inventory, crafting,
  cave with torch), pixel assertions that paired states differ where they must, and a two-launch
  persistence test with a persistent browser profile.
- Visual review: the verification stage reads the captured screenshots and records what is
  actually visible for Q2, Q4, Q5 and Q8.
- Offline evidence: no network references static scan plus a page load with the browser's network
  stack unused.

## Version disposition

The project bridge declares no version policy, so no version decision is made here and no version
source is changed. The seed's `version` value is left untouched; the product's display name/edition
label in `js/config.js` is presentation identity, not a release version.

## Risks accepted with this solution

- Relighting cost on every edit; mitigated by measuring and, if needed, trailing relight.
- `localStorage` behaviour across headless launches; mitigated by the two-run test and
  export/import evidence.
- Rendering cost at large viewports; mitigated by draw culling to visible tiles and a single canvas.
- The change report is waived by the user (`work_order.requires_report=false`,
  `work_order.report_skip_reason=user_waived`), so this delivery ends at the result document after
  verification.

## Approval request

Approve this solution: the accepted capability matrix above, the reversible deferral list, the
four-unit implementation boundary, and the verification strategy (seed checks plus new logic tests
and real-browser evidence). No unresolved material decision remains open.
