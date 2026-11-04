---
schema_version: 1
document_kind: node-artifact
content_language: en
audience: internal
work_order_id: "20261104-1337-2d-sandbox-game"
node_id: "rt_work-order-20261104-1337-2d-sandbox-game__dyn-1__implement-docs-polish"
feature_ids: []
orchestration:
  tree_ref: "/work/.xcoding/work-orders/20261104-1337-2d-sandbox-game/runtime/orchestration.xml"
---

# Implementation: Documentation and Polish

## Scope

Replaced the starter README with player-facing documentation and applied the final product review
fixes found while exercising the game at the reference viewport, a narrow viewport, night, a cave,
the packed inventory, and the reset/death flows.

## Changed Paths

- `README.md` — product description, offline launch, first steps, complete controls, world/progression
  reference, save behavior, project layout, verification commands, and the restricted-sandbox
  `HOME` note. Removed all starter wording.
- `index.html` — removed the HUD's high-frequency `aria-live` announcement while keeping the toast
  and feedback regions live; added the inventory feedback region.
- `css/style.css` — compacted the help panel to fit 960 × 600, added scrollbars, moved toast above
  title overlays, strengthened block-edge readability, and retained the 480 px responsive layout.
- `js/main.js` — pointerdown now records the actual pointer location before hover/place/mine; E closes
  the pack; manual save refuses to silently drop a held stack; new worlds create an initial save.
- `js/ui.js` — routed inventory-time feedback into an inline inventory message instead of a toast
  over the recipes; closing overlays clears stale toasts; pause New World always confirms.
- `js/render.js` — clipped underground texture strokes to the cave region, added shallow-depth ambient
  and a faint deep-cave visibility floor, and added subtle block seams/top highlights.
- `tests/foundations.test.js` — furnace/iron recipe-chain test (suite now 25 tests).

## Review Findings and Outcomes

| Finding | Outcome |
| --- | --- |
| Help panel "Back to the world" fell below the 600 px viewport | Compacted rows and spacing; button now ends at y≈568 at 960 × 600. |
| Tutorial toast obscured the pack recipe list | Inventory feedback is now an inline row; normal toast routed inside the pack. |
| Toast hidden behind title overlay on corrupt save | Toast z-index raised; corrupt notice visible above the title. |
| Pause "New World" skipped confirmation before the first save | Pause reset always confirms; title reset confirms when a save exists. |
| E did not close the pack because the overlay guard ran first | Reworked key handling; E toggles open/close. |
| Pointer clicks without a prior move used the default mouse origin | Pointerdown now updates the pointer position and hover before action. |
| Very dark deep caves read as an undifferentiated black wall | Added ambient depth light, a visibility floor, and edge seams; torch glow remains the local light source. |
| Saving with a held stack could lose that stack | Manual save refuses and explains while a stack is held. |
| README overstated the CDP probe's network behavior | Clarified that the game itself makes no requests and the probe only talks to local Chrome. |

## Evidence

- `node --test "tests/**/*.test.js"` — 25/25 pass.
- `python tools/page_check.py` — static pass; green ready marker; 145 canvas colour buckets.
- `python tools/play_probe.py` — 34/34 checks after the final polish, including 10/10 pointer clicks,
  60+ fps, no external requests, and no console errors.
- Help, start, inventory, day/night, cave/torch, narrow, corrupt-recovery, and pointer-state screenshots
  are kept under `artifacts/evidence/`.
- Final probe report: `tmp/final-probe4.json`.

## Convention Accounting

- English, UTF-8/LF, vanilla JavaScript, no new dependency or runtime network request.
- Project bridge verification commands preserved; docs describe the same actual controls as the UI.
- No project commit.

## Residual Risk

The fixed 16:9 canvas is scaled to the viewport; a portrait-heavy window stretches scene proportions
while the HUD/UI remain usable (verified at 480 × 700). The game is documented as best in a
landscape window. No blocking documentation or polish issue remains.
