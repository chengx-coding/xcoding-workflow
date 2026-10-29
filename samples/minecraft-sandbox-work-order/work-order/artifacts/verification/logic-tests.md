---
schema_version: 1
document_kind: node-artifact
content_language: "en"
audience: "internal"
work_order_id: "20261029-1459-2d-sandbox-game"
node_id: "rt_work-order-20261029-1459-2d-sandbox-game__dyn-1__logic-tests"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\runtime\\orchestration.xml"
---

# Verification — logic test suite

## Scope

Runs the project-defined logic test command from the project bridge and maps the assertions to the
functional acceptance conditions. Product code was not modified.

## Evidence

Command (project root):

```console
node --test "tests/**/*.test.js"
```

Outcome: exit code `0`; `tests 33`, `pass 33`, `fail 0`, `cancelled 0`, `skipped 0`, `todo 0`,
duration `119.9562ms`. Full output is retained at
`<workbench>/tmp/logic-tests-output.txt`.

Coverage mapping:

| Test file | Assertions | Acceptance covered |
| --- | --- | --- |
| `tests/world.test.js` (unchanged seed suite) | 6 | config contract, dimensions/seed, base ground line, bounded access, serialization, solidity |
| `tests/generation.test.js` | 6 | seed determinism, seed difference, column-10 invariant across four seeds, trees/leaves/varied heights, bottom-row seal, exact zero offset at column 10 |
| `tests/player.test.js` | 7 | gravity landing, wall stop, rising-edge jump, held jump height, ceiling stop, serialization, invalid restore |
| `tests/interaction.test.js` | 7 | mine reachable/empty/bounds/reach, place valid/player/occupied/unsupported/reach, solid-neighbour detection, reach distance |
| `tests/save.test.js` | 7 | round trip, missing, corrupt, invalid version, throwing-storage fallback, clear, malformed data |

## Findings

No required finding. The command exits zero and every functional bullet with a deterministic
assertion is covered: seeded terrain (including the original ground-line contract), gravity and
collision on both axes, jumping, reach and placement rules including the player-body exclusion, and
persistence serialization with a guarded fallback.

Coverage gaps recorded rather than hidden:

- The tests exercise modules without a DOM. Browser boot, rendering, input events and real
  `localStorage` are covered by the separate page check, the main-session browser probe and the
  independent visual review, not by this node.
- No long-session performance or memory test exists; the game is a small fixed-size world and the
  visual review inspects the live page.
- The storage fallback is proven with a hostile in-memory store, not with a browser policy that
  blocks `file://` storage; the runtime fallback path is the same code.

## Conclusion

PASS. The logic contract is satisfied with 33/33 tests and no regression in the six seed tests.
