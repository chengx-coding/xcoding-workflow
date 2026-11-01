---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-1819-mc-2d-sandbox"
node_id: "rt_work_order-20261030-1819-mc-2d-sandbox__dyn-1__repair-floor"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Repair — sealed world floor (review D1, plus D4 mitigation)

## Scope

Closes the review's high finding D1: the bottom two rows were ordinary mineable stone, so the world
was not sealed. The repair makes the floor unbreakable, renders it as a distinct bedrock face,
re-asserts it on every load, and proves the invariant in unit tests and a real browser J4 journey. It
also mitigates the low finding D4 (the palette covering the bottom row) so the floor is visible and
click-reachable.

## Evidence

### Changed paths

| Path | Change |
| --- | --- |
| `js/interaction.js` | `mineBlock` refuses any tile at or below `world.height - CONFIG.bedrockRows` with `The world floor is unbreakable.` and leaves the block untouched |
| `js/world.js` | `sealFloor()` re-asserts the bottom `bedrockRows` rows as stone on generation, JSON deserialization and RLE loading; exported for tests |
| `js/render.js` | `drawBedrockFace()` draws the floor rows as a dark, cracked bedrock face with a distinct colour regardless of the stored stone id |
| `js/main.js` | toggles an `is-tucked` class on the hotbar when the player is within five rows of the floor, so the palette slides down and the bottom row stays visible and clickable |
| `css/style.css` | tucked-palette styling (slide + fade, caption hidden) |
| `tests/interaction.test.js` | floor mine attempt refused, block unchanged, row above still mineable |
| `tests/terrain.test.js` | RLE and JSON loads re-seal the floor; every generated world is sealed |
| `tests/physics.test.js` | a 1000 tiles/s fall lands on the sealed floor instead of leaving the world |
| `tests/render.test.js` | the bottom rows render as the distinct bedrock face |
| `tools/journey_check.js` | new J4 journey: dig a shaft at column 100, inspect the underground background, stand on the floor, click it with the real mouse, assert refusal/unchanged floor, attempt the bottommost row, assert the palette tuck/restore, capture screenshots |
| `README.md` | documents the sealed unbreakable floor and underground backdrop |

### Commands and outcomes

```console
node --test "tests/**/*.test.js"
# tests 109, pass 109, fail 0

python tools/page_check.py
# ok true, static clean, marker distance 0.0, 251 canvas buckets

node tools/journey_check.js --out <workbench>/tmp/journeys
# ok true, checks 65, failed []
```

New J4 checks (all pass):

- `underground: the exposed background is dark, not sky` — pixel `[41,42,44,255]` in the dug shaft.
- `floor: the bottom row is still sealed after a mine click` — block id 3 before and after.
- `floor: the refusal explains the unbreakable floor` — visible toast `The world floor is unbreakable.`
- `floor: the bottommost row is also refused`.
- `floor: the player stands on the floor and cannot end up below it`.
- `floor: the palette tucks away so the bottom row stays reachable` and `floor: the palette returns after leaving the floor zone`.
- `underground.png` (SHA-256 `2149818C0194C1F2485BDC717E36202416D1ACB23ABECC9AB6F37BA2C9200A99`) and
  `underground-floor.png` (SHA-256 `8EF009D412C69E13F75035F64003519F394C383A08108771528F9E374F4FE6E5`)
  show the dark underground, the distinct bedrock band, the standing player and the refusal toast.

### Finding closure

| Finding | Closure |
| --- | --- |
| D1 high — no sealed world floor | Closed: unbreakable bottom rows, explicit refusal with reason, sealed on load, machine-checkable interaction/physics/terrain tests and an executed browser J4 journey that clicks the floor and observes the refusal |
| D4 low — palette covers the bottom row | Closed by the floor-zone tuck: the palette slides down near the floor, the tested floor tile is clickable at screen y≈524 while the palette top is ≈533, and it restores on leaving |

### Convention accounting

English, UTF-8/LF, two-space UMD style, no third-party or network assets, Node-loadable modules and
the status marker contract are all preserved. No commit was created. The declared verification
commands were re-run.

## Findings

- The sealed floor is now a real invariant enforced at three layers: generation/load sealing, the
  interaction rule and the physics floor; the renderer communicates it visually.
- The tuck behaviour resolves the palette occlusion without shrinking the palette or moving the world
  camera outside its bounds.
- No unrelated behavior changed: mining above the floor, placement, saving, pause and the palette all
  still pass their existing checks.

## Conclusion

D1 and D4 are closed with test-and-browser evidence. 109/109 logic tests, the page check and 65/65
journey checks are green.
