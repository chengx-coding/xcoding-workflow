---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-0000-minecraft-sandbox"
node_id: "rt_work-order-20261030-0000-minecraft-sandbox__dyn-1__impl-interaction-storage"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261030-0000-minecraft-sandbox\\runtime\\orchestration.xml"
---

# Implementation — interaction and persistence

## Scope

Approved implementation units U3 and U4 (interaction/inventory and persistence/settings):
capabilities M3, M4, M5, M7, M11, M17, M20 and the save half of the quality contract.

## Changed paths

- `project/js/interaction.js` (new) — screen-to-cell targeting, centre-based reach checks, mining and
  placement validation (bounds, air, adjacency, player overlap, stock), placement-target selection
  that prefers the neighbour nearest the player, inventory with per-block counts and stack cap,
  hotbar model with selection, number-key and wheel cycling, per-material hardness and hold-to-mine
  progress state.
- `project/js/storage.js` (new) — versioned `localStorage` game payload plus separate settings key,
  defensive schema validation, corrupt/missing/unavailable reasons instead of exceptions, and an
  injectable backend for tests.
- `project/tests/interaction.test.js`, `project/tests/storage.test.js` (new) — focused coverage for
  counts, selection, targeting, reach, mining, every placement refusal, placement success, mining
  progress, save/load, corrupt payloads, unavailable storage and settings.

## Validation

```console
node --test tests/interaction.test.js tests/storage.test.js
```

Result: 31 tests, 31 pass, 0 fail (log: `tmp/impl-interaction-tests.log`).

Browser evidence captured with the temporary CDP harness (`tmp/visual-verify.json`): a block was
mined in the page (leaves stock 12 -> 13), a block was placed next to a solid cell (grass stock
24 -> 23), the page was saved and reloaded, and both the world cells and the counts were restored
from `localStorage`; a changed seed also survived the reload. This proves the save/restore path in a
real `file://` page, not only in Node.

## Convention accounting

- C1 bridge — English, two-space indentation, UMD wrapper, Node-loadable modules: followed.
- C1 bridge — no network references: followed; storage is entirely local.
- C1 bridge — no formatter/linter: no formatting churn.
- No C2 signal applies.
- The refusal rules encode the request exactly: placement is refused inside the player, on occupied
  cells, out of reach, floating, and with empty stock; mining is refused out of reach, on air, and
  out of bounds.

## Residual risk

- The save payload is a whole-world JSON snapshot (about 40 KB); that is well inside
  `localStorage` quotas for this world size but would need chunking for a much larger world.
- `localStorage` availability differs per browser profile; the store degrades to an in-memory session
  with a visible toast instead of failing boot.
