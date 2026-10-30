---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-0000-minecraft-sandbox"
node_id: "rt_work-order-20261030-0000-minecraft-sandbox__dyn-1__impl-physics-camera"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261030-0000-minecraft-sandbox\\runtime\\orchestration.xml"
---

# Implementation — physics and camera

## Scope

Approved implementation unit U2: player gravity, running, jumping and solid collision, plus the
camera that follows the player and stays inside the world bounds (capabilities M2 and M6).

## Changed paths

- `project/js/player.js` — replaced the skeleton step with real physics: horizontal intent, gravity
  with a terminal fall speed, ground-only jumping, axis-separated sub-stepped AABB collision against
  block cells (no tunnelling at high fall speed), ground probing, world-bound clamping, facing and
  walk-time state, and exported box/overlap/support helpers. Kept `createPlayer` and the
  `stepPlayer(player, world, input, dt)` entry point the seed contract used.
- `project/js/camera.js` (new) — pure target computation that centres the player while clamping to
  the world edges, exponential follow smoothing, bound clamping, visible tile range for the renderer,
  and max-camera maths.
- `project/tests/player.test.js`, `project/tests/camera.test.js` (new) — focused coverage for landing,
  falling, wall and ceiling collision, jumping, no double jump, bounds, support detection, overlap,
  camera centring and clamping.

## Validation

```console
node --test tests/player.test.js tests/camera.test.js
```

Result: 21 tests, 21 pass, 0 fail (log: `tmp/impl-physics-tests.log`). Browser verification later
confirmed the player settles on the surface spawned by the generator and the camera renders the
followed view without leaving the world.

## Convention accounting

- C1 bridge — English comments/code, two-space indentation, UMD wrapper, Node-loadable modules: all
  followed; both modules load under Node with no DOM.
- C1 bridge — no network references: followed.
- C1 bridge — no formatting churn: existing field names and seed defaults preserved where the seed
  tests or README depend on them.
- No C2 signal applies.

## Residual risk

- The physics intentionally uses a simple constant-velocity horizontal model rather than
  acceleration curves; it is predictable and testable, and the visual review checks that movement
  reads smoothly in the browser.
- Collision resolution handles the one-tile overlaps produced by the configured speeds; a future
  teleport or very large step would need a larger substep budget.
