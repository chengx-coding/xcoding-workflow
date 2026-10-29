---
schema_version: 1
document_kind: node-artifact
content_language: "en"
audience: "internal"
work_order_id: "20261029-1459-2d-sandbox-game"
node_id: "rt_work-order-20261029-1459-2d-sandbox-game__dyn-1__page-check"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\runtime\\orchestration.xml"
---

# Verification — static and headless page check

## Scope

Runs the project-defined page check from the project bridge, including its static offline/asset
checks and its headless Chrome marker/canvas check, and inspects the captured screenshot. Product
code was not modified.

## Evidence

Command (project root):

```console
python tools/page_check.py --screenshot <workbench>/tmp/verify-page.png
```

Outcome: exit code `0`, `ok=true`. Full JSON is retained at
`<workbench>/tmp/page-check-output.json`.

| Check | Result |
| --- | --- |
| Static: required ids `game`, `status`, `hud`, `hotbar` | ok |
| Static: every local asset reference resolves | ok |
| Static: no external network reference in page-served files | ok (`problems: []`) |
| Status marker pixel | `[46, 204, 113]`, expected `[46, 204, 113]`, distance `0.0` |
| Canvas colour buckets (threshold 12) | `289` |
| Screenshot | `<workbench>/tmp/verify-page.png`, 960x600 |

Visual inspection of the captured frame:

- The brand, seed chip and save chip form a clear top-left hierarchy; sound and help controls sit
  top-right; the hotbar is anchored bottom-centre with an unmistakable gold-ringed Grass selection.
- The explorer is visible on a grass ledge with helmet, scarf, backpack and lantern; two textured
  trees, a sandy clearing, layered sky, drifting clouds, birds, a sun glow, parallax ridges and
  underground ore detail give the frame variety.
- The hint bar, status dot and hotbar do not collide; the frame is non-blank and contains no missing
  or error state.

## Findings

No required finding. The page satisfies the bridge's static and runtime contracts with exact marker
colour and 24x the minimum colour diversity.

Coverage gaps recorded rather than hidden:

- The page check renders a static boot frame; it does not mine, place, jump, open the guide or
  reload. Those paths are covered by the main-session browser probe and the independent visual
  review.
- The check samples the page at 960x600; a 1440x900 render is inspected separately for responsive
  hierarchy.

## Conclusion

PASS. The page is offline, locally complete, boots to `ready`, and renders a rich, non-blank canvas.
