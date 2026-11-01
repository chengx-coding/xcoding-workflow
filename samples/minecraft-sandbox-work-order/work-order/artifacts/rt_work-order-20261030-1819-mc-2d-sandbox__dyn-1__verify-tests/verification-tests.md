---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-1819-mc-2d-sandbox"
node_id: "rt_work-order-20261030-1819-mc-2d-sandbox__dyn-1__verify-tests"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Verification — tests and seed-test integrity (regression scope)

## Scope

Executed the project's declared logic-test command against the implemented page and verified that the
six seed tests are unchanged and still pass, then mapped the suite to the accepted capability matrix.

## Evidence

### Command and outcome

```console
cd C:\dev\xcoding-workflow-dev\wf-iterations\0.3.8\project
node --test "tests/**/*.test.js"

ℹ tests 104
ℹ pass 104
ℹ fail 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 208.149
```

Environment: Node v24.13.1 on Windows, no network or external service required.

### Test inventory

| File | Tests | Area |
| --- | --- | --- |
| `tests/world.test.js` | 6 | Seed contract (unchanged) |
| `tests/terrain.test.js` | 16 | Determinism, plateau, layers, trees, caves, bounds, RLE |
| `tests/physics.test.js` | 10 | Gravity, movement, jump, walls, ceilings, tunnelling, bounds |
| `tests/interaction.test.js` | 15 | Mining/placement rules, reach, overlap, support, refusals |
| `tests/inventory.test.js` | 7 | Counts, consume floor, serialization |
| `tests/persistence.test.js` | 9 | Round-trip, corruption, version, storage failures |
| `tests/timecycle.test.js` | 8 | Clock, phases, light, sky colours |
| `tests/camera.test.js` | 6 | Ease, clamps, reduced-motion snap |
| `tests/render.test.js` | 10 | Frame composition, day/night, hover, glass, particles |
| `tests/ui.test.js` | 6 | Hotbar model, selection, coordinates, targets |
| `tests/audio.test.js` | 6 | Lazy context, mute, failure modes |
| `tests/integration.test.js` | 5 | Mine → place → move → save → reload |

Total 104 tests, well above the accepted ≥52 threshold.

### Seed-test attestation

- `tests/world.test.js` SHA-256: `DA2FDCF9F9ACD4452534E64DB2FC2CD10F8DA4C09C412B898B82490CE7DA3831`.
- The file was never edited by either implementation unit; the analysis recorded its six-test content
  before implementation, and the current file still contains exactly these six tests:
  1. `config exposes the seed contract`
  2. `createWorld has the configured dimensions and seed`
  3. `the generated world has a ground line and sky`
  4. `block access is bounded`
  5. `serialization round-trips blocks and seed`
  6. `solidity treats air as walkable`
- The seed assertions are intact: grass at x=10 row 41, dirt at row 42, stone in the last row, air at
  (0,0), bounded `getBlock`/`setBlock`, `serializeWorld`/`deserializeWorld` round-trip and `isSolid`.
  All six pass in the run above.

### Capability mapping

| Capability | Evidence |
| --- | --- |
| C1 deterministic terrain | terrain determinism/layer/plateau tests (16) |
| C2 movement, gravity, jump, collision | physics tests (10), including no tunnelling at 1000 tiles/s |
| C4 placement rules and refusals | interaction tests (15), every refusal asserts an unchanged world |
| C7 persistence | persistence (9) and integration (5) round-trip tests |
| C11 tests and seed preservation | 104/104 pass, seed file unchanged, six seed tests present |
| C16 52-test inventory | 104 ≥ 52, seed tests included |
| J1–J11 unit-level backing | mine/place/inventory/save-load/pause-clock/camera-clamp/hotbar/time tests |

### Gaps

- Unit tests cannot prove browser-level rendering pixels, real keyboard/mouse input, real reload, or
  the visible-state contract; those are covered by `verify-page` and `verify-journeys`.
- No code-coverage tooling is configured in the project; coverage is mapped by behaviour, not by a
  line percentage. That is a recorded gap, not a failure.

## Findings

- The declared command passes with real counts and no skipped or todo tests.
- The seed tests are intact and additive coverage was used instead of weakening them.
- The suite covers the accepted logic surface; visual/browser journeys are deliberately deferred to
  the page and journey verification nodes.

## Conclusion

Regression verification passes. No test gap blocks the work order; the browser-level gaps are covered
by the next two verification nodes.
