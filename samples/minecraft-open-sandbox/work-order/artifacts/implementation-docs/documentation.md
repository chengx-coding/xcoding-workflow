---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261101-2045-open-sandbox-xc-2"
node_id: "rt_work-order-20261101-2045-open-sandbox-xc-2__dyn-1__documentation"
feature_ids: []
orchestration:
  tree_ref: ".xcoding/work-orders/20261101-2045-open-sandbox-xc-2/runtime/orchestration.xml"
---

# Documentation implementation

## Changed paths

- `README.md` — rewritten for the delivered game: product summary, run instructions, a complete
  controls table, the implemented Minecraft-inspired systems, the recorded deliberate scope, saving
  and recovery behaviour, the three verification commands with what each proves, and the final module
  layout.

## Accuracy checks

- Controls table compared against `js/config.js` `controls` (10 rows) and against the rendered help
  overlay, which is generated from the same array; the browser check asserts 10 help rows.
- Crafting amounts copied from `config.recipes`: 1 wood -> 4 planks, 2 planks -> 4 sticks, 1 stick +
  1 coal -> 4 torches, 3 planks + 2 sticks -> wooden pickaxe, 3 stone + 2 sticks -> stone pickaxe.
- Save key, autosave interval, world size, day length and tool gating copied from `config.js`.
- Verification commands are exactly the project bridge commands plus the new
  `node tools/browser_check.mjs`; the browser-check requirements (Node 22+ for built-in `WebSocket`,
  local Chrome/Edge) are recorded.
- The README does not claim survival, mobs, redstone or other absent systems; the deliberate scope
  section matches the analysis record.
- No network reference, external asset, font or CDN is named or required.

## Validation

- Manual cross-check of every documented number against the source files listed above.
- The documented commands were executed in this work order: 41/41 unit tests, `page_check.py`
  `ok=true`, `browser_check.mjs` `ok=true` with 16 steps and zero console errors.
- The page's own help overlay remains the in-game copy of the controls table, so the two cannot drift
  without the browser check's row assertion failing.

## Residual risk

- The README is prose and is not executed by the test suite; numeric documentation can still drift if
  a future change edits `config.js` without updating it. The browser check protects the control list
  and the work-order verification records protect the command list.
