---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261028-1731-implement-minecraft-sandbox"
node_id: "rt_work-order-20261028-1731-implement-minecraft-sandbox__dyn-1__analysis-evidence"
feature_ids: []
orchestration:
  tree_ref: "C:/dev/xcoding-workflow-dev/minecraft-sandbox-workshop/.xcoding/work-orders/20261028-1731-implement-minecraft-sandbox/runtime/orchestration.xml"
---

# Analysis Evidence: Offline 2D Sandbox

## Scope

Evidence for implementing the playable offline 2D sandbox in the consumer project. Read-only
inspection of the seed project, the verification harness, the project bridge and the work-order
request; no product code was modified.

## Confirmed facts and current state

| Surface | Evidence | Current behavior |
| --- | --- | --- |
| Page shell | `index.html` | Canvas `#game` (960x540), `#hud`, four-slot `#hotbar`, and the `#status` marker with `data-state="booting"`; loads five local scripts. No control hint line. |
| Styles | `css/style.css` | Dark page around a fixed 960x540 canvas, panel HUD, hotbar slots and green/red status-marker states. |
| Constants | `js/config.js` | Block ids `air=0, grass=1, dirt=2, stone=3, wood=4, leaves=5`; `tileSize=24`, world `128x64`, `gravity=0.55`, `moveSpeed=3.2`, `jumpSpeed=8`, `reach=5`, `saveKey`. There is no `seed` property, so `createWorld(config.seed)` currently receives `undefined`. |
| World | `js/world.js` | `createWorld` fills a completely flat surface at `floor(height * 0.65)` with one grass row, three dirt rows, then stone. Blocks are a `Uint8Array`; get/set are bounds-checked; serialization is JSON. No seeded terrain, no trees, no spawn helper. |
| Player | `js/player.js` | `createPlayer` returns `{x, y, vx, vy, onGround, width: 0.7, height: 1.8}`. `stepPlayer` applies horizontal intent, always adds gravity, and moves without any tile collision or jumping. |
| Renderer | `js/render.js` | Sky gradient, visible tiles, and a simple player rectangle. Camera clamping exists only as a local helper in `main.js`; no exported camera function and no target highlight. |
| Boot/loop | `js/main.js` | Renders exactly one frame, marks `#status` ready, selects the first hotbar slot, and requests a render loop with no update step. There is no keyboard/mouse input, no save/load, no HUD hint, and the HUD says the features are not implemented. |
| Tests | `tests/world.test.js` | Six seed tests: config contract, dimensions/seed, flat ground line at `x=10`, bounded block access, serialization round-trip, and solidity of air. |
| Harness | `tools/page_check.py` | Static checks for ids `game/status/hud/hotbar`, external references and local assets; headless Chrome screenshot; samples the status-marker pixel for `#2ecc71` and requires at least 12 colour buckets in the canvas. Supports `--screenshot`. |
| Documentation | `README.md` | Describes the target controls and module layout but still calls the repository a seed whose features are implemented by the work order. |
| Bridge | `.xcoding/WORKFLOW.md` | English, UTF-8/LF, no commit, no build, no third-party/CDN/network, `file://` operation, preserved status contract, Node-loadable modules, add tests. Verified checks: `node --test "tests/**/*.test.js"` and `python tools/page_check.py`. |
| Host | Bridge declaration and current session | Node.js 24, Python 3.12 and Google Chrome are available; no formatter or linter is configured. |

## Requirement gap matrix

| Requirement | Current state | Required change |
| --- | --- | --- |
| Deterministic procedural terrain from a numeric seed with grass, dirt and stone | Flat, seedless terrain | Add a default numeric seed, a seeded deterministic height function, layered soil/stone, and deterministic trees |
| Player movement, gravity, jumping, solid-tile collision | Intent and gravity only | Rewrite the player step with AABB collision, axis-separated resolution, jump and ground detection |
| Left-click mining within reach; right-click placement in an empty adjacent cell that never overwrites the player | None | Add pure interaction helpers and wire pointer input |
| Hotbar with at least four block types, number-key selection and visible selected state | Four static slots, first slot highlighted once | Wire keys 1-4, clicks, `is-selected` and `aria-pressed` |
| Camera follows the player and stays in world bounds | One local clamp call | Export a pure camera function and recompute every update |
| Save/load world and player through `localStorage`, restored on load | World JSON helpers only | Add a storage-injected save module and boot restore |
| Readable page with a control hint line | Skeleton HUD text | Add a persistent hint line and selection readout |
| Architecture and controls in `README.md` | Target description | Document the implemented behavior, controls, run instructions and checks |
| Tests for determinism, bounds, collision, placement and save/load | Six seed tests only | Add focused Node tests without weakening `world.test.js` |
| No external libraries/CDNs/fonts/network; `file://` support | Compliant | Preserve; keep all code local and DOM APIs standard |

## Impact and risks

- **Seed-test invariant.** `tests/world.test.js` asserts grass at `x=10, y=41`, dirt below it and stone
  at the bottom. A hilly heightmap everywhere would break that test. Mitigation: keep a flat west
  spawn plateau (columns `0..23` at the original ground line), put hills east of it, and spawn the
  player on the plateau. This preserves the seed test and gives a safe start area.
- **Physics constants are untuned.** `jumpSpeed=8` with `gravity=0.55` would lift the player roughly
  58 tiles. Mitigation: retune the frame-based constants (about 3.4-tile jump, 10-11 tiles/second
  movement) and verify the feel with focused tests and a rendered screenshot.
- **Tunnelling through blocks.** Large per-frame movement can skip a tile. Mitigation: substep
  movement and snap the player to the collided tile edge.
- **`file://` storage availability.** Some browsers restrict `localStorage` on file URLs. Mitigation:
  wrap storage access in `try/catch`, continue with a fresh world when unavailable, and never let
  persistence failure break the game loop or the status marker.
- **Page-check timing.** The harness screenshots after a virtual-time budget and samples the status
  pixel; the marker must be green by then. Mitigation: set `ready` after the first successful render
  and keep the render loop free of asynchronous prerequisites.
- **Canvas blankness threshold.** The harness requires at least 12 colour buckets. Mitigation: keep
  the sky gradient, multiple block colours, per-block texture accents and the player rendering.
- **World payload size.** A JSON array of 8,192 bytes is roughly 16-30 KB, well inside typical
  `localStorage` quotas; the serializer already uses this shape.
- **No feature baseline and no commit.** `feature_ids=[]`; the bridge forbids a project commit. The
  implementation must not create a feature directory or a commit.
- **No user approval channel.** The main session must record the solution gate as `approved` with a
  concrete decision and continue; no user-question tool may be called.

## Alternatives considered

1. **Terrain generation.** Options: (a) keep a flat world with only seeded surface decoration;
   (b) per-column independent PRNG heights; (c) smooth seeded multi-sine/value heightmap with a flat
   spawn plateau and deterministic trees. Option (a) is not convincingly procedural; option (b) is
   jagged and hard to traverse. Option (c) is deterministic, readable and preserves the seed test.
2. **Physics units.** Options: (a) keep the skeleton constants; (b) retune gravity/move/jump to
   frame-based units. Option (a) produces an unplayable jump; option (b) is required for a playable
   game. Frame-based fixed-step updates keep tests deterministic.
3. **Collision resolution.** Options: (a) revert the whole move on overlap; (b) axis-separated AABB
   with edge snapping and substeps. Option (b) gives stable wall sliding and ground contact and is
   testable.
4. **Interaction placement.** Options: (a) implement pointer mapping and rules inside `main.js`;
   (b) add a pure `js/interaction.js` module. Option (b) makes reach, placement and player-overlap
   rules directly testable without a DOM.
5. **Persistence.** Options: (a) call `localStorage` directly from `main.js`; (b) add `js/save.js`
   with an injected storage interface. Option (b) allows a real round-trip test with an in-memory
   storage fake and keeps `main.js` thin.
6. **Rendering.** Options: (a) keep flat rectangles; (b) add procedural per-tile texture accents,
   a target outline and a slightly more readable player. Option (b) improves readability and the
   harness colour count without any asset or network dependency.
7. **Tests.** Options: (a) extend `world.test.js`; (b) add new focused test files and leave the seed
   assertions untouched. Option (b) prevents accidental weakening of the seed contract.

## Unknowns and unresolved decisions

- No product-owner review is possible in this session; the solution gate is a recorded main-session
  decision, not a claim of human approval.
- No real device/browser matrix is available beyond the declared headless Chrome harness; touch input
  and mobile layout are out of scope.
- The visual "feel" of the retuned physics can only be smoke-checked through the rendered screenshot
  and logic tests, not by a human play session.

## Conclusion

The seed is a working shell but has none of the interaction, collision, persistence or procedural
generation logic. The lowest-risk coherent design is to keep the existing UMD module layout and add
two pure modules (`interaction.js`, `save.js`), extend `world.js` with seeded terrain, rewrite the
player step with AABB collision, extend the renderer with camera and target drawing, and wire the
whole thing in `main.js`. The existing flat ground test is preserved by a flat spawn plateau.
