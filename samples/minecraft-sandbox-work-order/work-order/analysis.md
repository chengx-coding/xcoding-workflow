---
schema_version: 1
document_kind: work-order-analysis
content_language: en
work_order_id: "20261028-1731-implement-minecraft-sandbox"
feature_ids: []
orchestration:
  main_tree_ref: "C:/dev/xcoding-workflow-dev/minecraft-sandbox-workshop/.xcoding/work-orders/20261028-1731-implement-minecraft-sandbox/runtime/orchestration.xml"
---

# Analysis: Offline 2D Sandbox

## Evidence and current state

The consumer project is a static seed, not an incomplete game. `index.html` already fixes the page
contract: a 960x540 `#game` canvas, `#hud`, a four-slot `#hotbar` and the `#status` marker whose
`data-state` must move from `booting` to `ready` on a successful first frame. `tools/page_check.py`
enforces that contract together with the absence of external network references, the existence of
every local asset, the green marker pixel and at least 12 canvas colour buckets.

The JavaScript is split into five UMD modules so Node can require the logic without a DOM. Today
`js/config.js` has block ids, a 128x64 world, 24-pixel tiles and untuned physics but no numeric seed;
`js/world.js` generates a completely flat surface and supports bounded get/set plus JSON
serialization; `js/player.js` only applies intent and gravity, with no collision or jumping;
`js/render.js` draws a sky, flat tiles and a rectangle player; and `js/main.js` renders one frame,
marks the page ready, highlights the first hotbar slot and starts an empty render loop. The seed test
file has six tests that fix the flat ground line at `x=10`, bounded block access, serialization and
solidity. The detailed file-by-file evidence is recorded in
`artifacts/analysis-evidence/analysis-evidence.md`.

The project bridge declares the verification commands (`node --test "tests/**/*.test.js"` and
`python tools/page_check.py`), the no-network/no-build/`file://` constraints, the status-marker
contract, UTF-8/LF text, English documentation, no project commit, and the instruction not to weaken
the seed tests. The L1 convention scan found no additional project instruction files; the applicable
declared rules come from the bridge and the checkout-level `AGENTS.md`, with no conflict.

## Reconciliation

There are no related features (`feature_ids=[]`), so there is no feature baseline to reconcile and no
feature directory may be created. The approved target intent comes from the user request, the
functional scope in the work order, and `project/README.md`; the current code and tests are evidence
of present behavior, not an approved baseline.

The target and the seed are compatible with one important constraint. The seed test asserts grass at
`x=10` on the `floor(height * 0.65)` line, dirt below it and stone at the bottom. A height map that
varies at every column would break that assertion. The reconciled design therefore keeps a flat west
spawn plateau over the original ground line and begins procedural hills east of it. This preserves the
seed test without weakening it, keeps a safe spawn area, and still produces deterministic,
seed-dependent terrain elsewhere. The existing world dimensions, tile size, block ids, serializer
shape and module layout remain compatible; the seed property and the retuned physics are additive
changes to shared constants.

No convention conflict or ambiguity was found. The one recorded deviation is intentional: no project
Git commit will be created, as both the bridge and the user decision require.

## Impact and risks

The change is bounded to the consumer project: `index.html`, `css/style.css`, `js/config.js`,
`js/world.js`, `js/player.js`, `js/render.js`, `js/main.js`, new `js/interaction.js` and `js/save.js`,
new test files, and `README.md`. There is no build step, dependency, migration, feature directory,
network call or public API outside this sample page. The `localStorage` payload is new but versioned;
existing saved data does not exist because the seed never wrote any.

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Hilly terrain breaks the flat-ground seed test | Required check fails | Flat spawn plateau at the original ground line; hills east of it |
| Untuned skeleton physics makes the game unplayable | Jump of roughly 58 tiles | Retune to frame-based units (about 3.4-tile jump, 10-11 tiles/second) |
| Tunnelling through solid blocks at speed | Player passes through terrain | Axis-separated AABB collision, edge snapping and movement substeps |
| `localStorage` unavailable on `file://` | Boot failure or red status | Guarded storage access; fall back to a fresh world, never throw |
| Marker sampled before ready | Page check fails | Mark ready synchronously after the first successful render |
| Canvas colour count below the harness threshold | Page check fails | Sky gradient, five block colours, texture accents and player drawing |
| Placement overwrites the player | Functional defect | Explicit player-AABB overlap rejection in the placement rule |
| No user approval channel | Gate cannot wait | Record the gate decision in the main session and continue |
| Project commit accidentally created | Violates bridge and sample ownership | No commit commands; record the decision in the result |

## Alternatives

**Terrain.** A flat world with seeded decoration does not satisfy a convincing procedural terrain; a
per-column independent random height is jagged and hard to traverse. A smooth seeded multi-sine height
map with a flat spawn plateau and deterministic trees gives readable hills, a safe start and
reproducible output.

**Physics units.** Keeping the skeleton constants produces an unusable jump. Retuning gravity,
movement and jump to frame-based values, with a fixed update step, is necessary for a playable game
and leaves the logic deterministic for tests.

**Collision and interaction.** Reverting the whole movement on overlap is simple but produces sticky
walls. Axis-separated AABB resolution with edge snapping and substeps supports stable wall sliding and
ground contact. Putting reach, placement and player-overlap rules in a pure `js/interaction.js`
module keeps them testable without a DOM; burying them in `main.js` would make the required placement
tests need a browser.

**Persistence.** Calling `localStorage` directly from `main.js` is shorter but untestable in Node. A
`js/save.js` module that accepts an injected storage object permits an in-memory round-trip test while
`main.js` still passes the real `localStorage` and guards unavailable storage.

**Tests.** Extending `tests/world.test.js` risks weakening the seed assertions. New focused test files
for terrain, player, interaction, save/load and camera keep the seed contract intact and make the
required coverage explicit.

## Conclusion

The implementation can proceed as a cohesive change inside the existing module layout. The evidence
supports one design: seeded terrain with a flat spawn plateau, retuned frame-based physics with AABB
collision, a pure interaction module, a storage-injected save module, an extended renderer with a
clamped follow camera and target outline, and a fully wired `main.js`. The seed tests stay untouched,
the required checks remain the acceptance authority, and the report and commit are explicitly waived.
