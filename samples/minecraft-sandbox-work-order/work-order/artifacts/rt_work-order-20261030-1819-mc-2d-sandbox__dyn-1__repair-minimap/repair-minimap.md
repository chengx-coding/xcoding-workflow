---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261030-1819-mc-2d-sandbox"
node_id: "rt_work_order-20261030-1819-mc-2d-sandbox__dyn-1__repair-minimap"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-iterations\\0.3.8\\project-xc-workshop\\.xcoding\\work-orders\\20261030-1819-mc-2d-sandbox\\runtime\\orchestration.xml"
---

# Repair — spatial aid with a live minimap (review D3)

## Scope

Closes the review's medium finding D3: a 128x64 sandbox world with underground navigation had no map
or spatial aid beyond coordinates. The repair adds a compact live minimap showing the surface profile,
the current camera viewport and the player position, wired into the existing HUD.

## Evidence

### Changed paths

| Path | Change |
| --- | --- |
| `index.html` | `#minimap-panel` under the top bar with a `MAP` label, live seed and a 180x64 `#minimap` canvas |
| `css/style.css` | glass panel styling at 960/1280 and a scaled variant at the narrow breakpoint |
| `js/render.js` | `renderMinimap(ctx, world, player, camera, size)` draws the sky band, the surface profile with sand/grass line, the underground tint, the camera viewport rectangle and the player dot, with a border |
| `js/main.js` | DPR-aware minimap sizing, per-frame rendering, seed label updates, resize handling |
| `tests/render.test.js` | minimap columns, player dot and viewport rectangle are asserted |
| `tools/journey_check.js` | orientation checks: minimap exists, is non-blank, and its image checksum changes after a player teleport |
| `README.md` | documents the live minimap and the renderer |

### Commands and outcomes

```console
node --test "tests/**/*.test.js"
# tests 121, pass 121, fail 0

python tools/page_check.py
# ok true, static clean, marker distance 0.0, 252 canvas buckets

node tools/journey_check.js --out <workbench>/tmp/journeys
# ok true, checks 70, failed []
```

New checks (all pass):

- `orientation: the minimap exists and is non-blank` — the canvas renders more than five colour buckets.
- `orientation: the minimap tracks the player` — the image checksum changes after teleporting the
  player from x=20 to x=40.
- The final 960x600 frame (`final-960x600.png`, SHA-256
  `55A50F1C79604A9EBD1382B9CEFC2117F82C6F3BCBE303F6926459C569753F94`) shows the MAP panel at the upper
  right with the seed, the surface profile, the viewport rectangle and the amber player dot; the
  1280x800 frame (`wide-1280x800.png`, SHA-256
  `889F492EF9AB9D53853C28349DA83EB907ECB9F3E842A27292CA415F95670040`) keeps it inside the layout.

### Finding closure

| Finding | Closure |
| --- | --- |
| D3 medium — no minimap/spatial aid | Closed: a live minimap shows the world profile, the viewport and the player; it is tested at the renderer level and proven live in the browser, including movement tracking |

Design note: the minimap is a surface-profile map at 180x64, not a full block-by-block map; it is
deliberately compact so it stays legible and cheap, and it follows the same seed as the world.

### Convention accounting

English, UTF-8/LF, two-space UMD style, no external assets, Node-loadable modules and the status
marker contract preserved; no commit created; declared checks re-run.

## Findings

- The map sits in the existing glass HUD language and does not collide with the top bar, hotbar or hint
  line at 960 or 1280; the narrow 800 layout scales it.
- No regression in the prior 68 journey checks; the two new orientation checks bring the probe to 70.
- The minimap seed label updates on load, seed change and restore through the HUD update.

## Conclusion

D3 is closed with renderer tests and live browser evidence. 121/121 tests, page check green, 70/70
journey checks.
