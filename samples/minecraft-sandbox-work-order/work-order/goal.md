---
schema_version: 1
document_kind: work-order-goal
content_language: en
work_order_id: "20261028-1731-implement-minecraft-sandbox"
feature_ids: []
orchestration:
  main_tree_ref: "C:/dev/xcoding-workflow-dev/minecraft-sandbox-workshop/.xcoding/work-orders/20261028-1731-implement-minecraft-sandbox/runtime/orchestration.xml"
---

# Work Order Goal

## Requested outcome

Implement the playable, offline 2D Minecraft-style sandbox that the consumer project
(`samples/minecraft-sandbox-work-order/project`) currently only seeds: the page shell, module
skeleton and verification harness exist, but terrain generation, player physics, block interaction,
the hotbar, camera follow, persistence and the user-facing documentation are unfinished. The finished
page must be a complete game that works when `index.html` is opened directly from the file system.

## Scope and constraints

In scope:

- Deterministic procedural terrain from a numeric seed with at least grass, dirt and stone.
- A player with horizontal movement, gravity, jumping and tile collision that cannot pass through
  solid blocks.
- Left-click mining within reach and right-click placement of the selected block in an empty adjacent
  cell, never overwriting the player.
- A hotbar with at least four block types, number-key selection and a visible selected state.
- A camera that follows the player and remains inside the world bounds.
- Save and load of world and player state through `localStorage`, restored on page load.
- A readable page with a control hint, and a short architecture and controls section in
  `project/README.md`.
- New Node logic tests covering the required behavior, without weakening the seed tests.

Constraints:

- No third-party libraries, CDNs, external fonts or runtime network requests; `index.html` must keep
  working from `file://`.
- Preserve the `#status` marker contract: `data-state="booting"` before boot, `data-state="ready"`
  after a successful first frame, and a red error state on failure.
- Preserve the existing local file layout and keep the browser modules loadable in Node.
- Do not create a project Git commit; the enclosing repository owns the sample's scoped commit.
- The change-report stage is waived by the user: `work_order.requires_report=false` and
  `work_order.report_skip_reason=user_waived`.
- Runtime state is read and written only through `xcoding runtime ...`; temporary files stay under
  the workbench `tmp/` directory and are never declared as artifacts.

Lifecycle decisions fixed for this work order: full `xc-work operation=run`, `mode=change`,
`document_language=en`, `feature_ids=[]`, analysis required, solution required, and the solution
approval gate required. With no user approval channel available, the main session records every gate
decision explicitly and continues.

## Acceptance conditions

1. `node --test "tests/**/*.test.js"` passes and covers terrain determinism, block get/set bounds,
   collision resolution, placement rules and save/load round-tripping.
2. `python tools/page_check.py` passes: no external network references, required elements present,
   the page status marker reports success, and the rendered canvas is not blank.
3. The `#status` marker contract and the existing local file layout are preserved.
4. `project/README.md` describes what was built, how to run it, the controls and the test commands.
5. Every declared artifact lives under the work order workbench, with test output recorded as
   evidence.
