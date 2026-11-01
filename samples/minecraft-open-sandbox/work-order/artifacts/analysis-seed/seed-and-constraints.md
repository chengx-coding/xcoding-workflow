---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261101-2045-open-sandbox-xc-2"
node_id: "rt_work-order-20261101-2045-open-sandbox-xc-2__dyn-1__seed-and-constraints"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261101-2045-open-sandbox-xc-2/runtime/orchestration.xml"
---

# Seed, constraints and verification surface

## Scope and method

Read every seed file, ran the project bridge's verification commands, and inspected the local browser
tooling. No product code was modified. All statements below are confirmed by a file, a command
outcome, or a direct observation; hypotheses are labelled.

## Current implementation evidence

The project is a 715-line plain HTML/CSS/JavaScript seed (line counts measured with
`Get-Content | Measure-Object -Line`):

| File | Lines | Current behaviour |
| --- | ---: | --- |
| `index.html` | 27 | Canvas, HUD, 4-slot hotbar, status dot; five classic scripts loaded in order |
| `css/style.css` | 83 | Fixed 960x540 canvas, dark page, hotbar and status styling |
| `js/config.js` | 38 | Frozen constants: 24 px tiles, 960x540 view, 128x64 world, gravity, save key, 6 block ids |
| `js/world.js` | 91 | Flat world (grass/dirt/stone at 65% height), bounded get/set, JSON serialize/deserialize |
| `js/player.js` | 33 | Placeholder gravity and horizontal velocity only; no collision or jump |
| `js/render.js` | 76 | Sky gradient, visible tiles, block rectangle, player rectangle |
| `js/main.js` | 54 | Boots the world, draws one frame, then a render loop; exposes `window.__sandbox` |
| `tests/world.test.js` | 50 | 6 `node:test` cases over config, dimensions, ground line, bounds, serialization, solidity |
| `tools/page_check.py` | 242 | Static asset/network scan, headless Chrome screenshot, status-marker pixel and canvas-colour checks |
| `README.md` | 21 | Run and check instructions plus the seed layout |

Command outcomes before any change:

- `node --test "tests/**/*.test.js"` -> 6 tests, 6 pass, 0 fail.
- `python tools/page_check.py --screenshot .../tmp/seed-baseline.png` -> `ok=true`; static checks pass;
  status marker pixel `[46,204,113]`, distance 0.0; canvas colour buckets 27; screenshot captured.
- Environment: Node v24.13.1 (global `WebSocket` available), Python 3.12.10, Chrome and Edge present.
- `git log` reports the project branch has no commits yet; the worktree is untracked. No project
  commit may be created by this work order.

The seed is a rendering skeleton, not a game: there is no input handling, no collision, no mining,
no placing, no inventory, no saving and no help. `README.md` explicitly leaves movement, mining,
building, crafting, progression, saving and UI to the implementation.

## Constraint facts (project bridge)

`index.html` must run from `file://` with no build step, framework, external library, CDN or network
request. Code, comments, README and work-order documents are English and UTF-8/LF. The seed tests and
page check are the declared verification entry points and must not be weakened. Temporary process
files belong under the work order `tmp/`. The change report is waived.

## Verification surface

1. **Node unit tests** can require `js/*.js` directly because the seed uses a UMD wrapper
   (`module.exports` plus a browser global). New simulation modules should keep that pattern so game
   logic is testable without a browser.
2. **`tools/page_check.py`** proves the shell, local assets, absence of network references, a
   non-blank canvas and the green status pixel. It does not prove interaction, and its canvas-colour
   check samples only the top 540 px of the viewport.
3. **A real interactive browser check is missing.** Headless Chrome can be driven over the DevTools
   Protocol; Node 24 provides a built-in `WebSocket`, so a no-dependency harness can dispatch real
   key and mouse events, read game state, reload the page, and capture screenshots. This is the right
   instrument for the playability and persistence acceptance conditions.
4. Seed tests impose compatibility constraints (see next section), so the planned verification adds
   tests and browser evidence rather than replacing the seed suite.

## Seed-test compatibility constraints (material)

`tests/world.test.js` is explicit and must keep passing unchanged. Its assertions constrain the new
world generator:

- `world.width === config.worldWidth`, `world.height === config.worldHeight`, `world.seed ===
  config.seed >>> 0`, and `world.data.length === width * height`. Changing the configured size is
  allowed; changing the storage shape is not.
- `getBlock(world, 0, 0) === air`.
- `getBlock(world, 10, ground) === grass` and `getBlock(world, 10, ground + 1) === dirt` where
  `ground = floor(world.height * 0.65)`.
- `getBlock(world, 10, world.height - 1) === stone`.
- Bounded `getBlock`/`setBlock`; `serializeWorld`/`deserializeWorld` round-trip blocks and seed;
  `isSolid` treats air as walkable and the bottom row as solid.

Consequences for the design:

- The height map must equal `floor(height * 0.65)` at column 10 exactly. A smooth amplitude ramp that
  is zero near the left edge satisfies this while allowing hills further out.
- Caves must not remove the top three sub-surface tiles at column 10, and the bottom row must remain
  `stone` (so an unbreakable floor is a *rule*, not a new bedrock block, or the block id would change).
- `serializeWorld` should keep its documented JSON shape; a compact RLE form can be added alongside it
  for the save file. Keeping both is cheap and avoids weakening the seed test's meaning.

## Risks and unknowns

| Risk | Evidence | Mitigation |
| --- | --- | --- |
| `localStorage` may be unavailable or isolated under `file://` | Not yet tested; page check never writes storage | Probe with the browser harness before relying on it; wrap every access in try/catch; keep an in-memory fallback and a visible warning; keep the save format versioned and validated |
| Canvas input coordinates under CSS scaling | Seed canvas is fixed 960x540; planned responsive CSS can scale it | Map pointer coordinates through `getBoundingClientRect()` and the internal canvas size; verify with real mouse events |
| Frame-time-dependent physics | Seed player step is per-frame, not per-second | Use a fixed-step accumulator with a clamped delta; unit-test collision independently of frame rate |
| Lighting cost on every edit | Full light recomputation is O(world) | Recompute only on world edit or quantized time bucket; measure in browser |
| Save size and corruption | 192x96 tiles as JSON is large | RLE encode, hash/version the payload, validate dimensions and values, fall back to a new world with a message |
| No build step means global script order | Seed pattern | Keep UMD modules and a documented load order; unit tests import the same files |
| Test determinism | World generation, time of day and particles | Seeded PRNG only; inject time into logic; disable particles/audio in headless checks |
| The page check's canvas sampling | It samples only the top 540 px and the status pixel | Keep the canvas inside that region and the status dot fixed; do not weaken the check |

## Conclusion

The seed is a clean, testable shell with a deliberately small verification surface. The design can
grow into a real game without violating any seed assertion if the height map is anchored at column 10,
the bottom row stays `stone`, and the serialization contract is preserved. The largest unproven
assumption is `file://` storage, which must be verified with a real browser rather than assumed.
