---
schema_version: 1
document_kind: node-artifact
content_language: "en"
audience: "internal"
work_order_id: "20261029-1459-2d-sandbox-game"
node_id: "rt_work-order-20261029-1459-2d-sandbox-game__dyn-1__visual-repair"
feature_ids: []
orchestration:
  tree_ref: "C:\\dev\\xcoding-workflow-dev\\wf-ablation\\standard-sample\\workspace\\workshop\\.xcoding\\work-orders\\20261029-1459-2d-sandbox-game\\runtime\\orchestration.xml"
---

# Visual repair — review observations closed

## Scope

Addressed the four non-blocking observations from the independent visual review without changing
functional behavior, the seed tests, the offline contract, the `#status` marker or the approved
scope. Product code and the page presentation were edited; the evidence was re-rendered and
re-checked.

## Findings addressed

### Observation 1 — the field guide scrolled at 960x600

- Shortened the control descriptions in `index.html` (`Mine within reach (hold to repeat)`,
  `Place a clear, supported block`, `Pick a material, or scroll`, `Open or close this guide (Esc)`,
  `Mute or unmute sound`).
- Added a `@media (max-height: 720px)` compact panel: tighter panel padding, head margin, heading
  size, control and legend spacing, seed-form spacing and button padding.
- Made `.panel-head` sticky with a matching gradient so the close control remains visible if a short
  viewport still scrolls.
- Closure evidence: at a 942x504 viewport (shorter than the 960x600 contract), the panel measured
  `scrollHeight=471`, `clientHeight=471`, panel bottom `489`, reset row bottom `450`, seed hint bottom
  `472`, `fits=true`. Captures: `tmp/repair-overlay-960.png` (first open, all actions visible) and
  `tmp/visual-overlay.png` (1182x664, all content visible). The 1440x900 layout still fits with the
  normal spacing (`tmp/repair-1440.png`).

### Observation 2 — deep cave air read as near-black void

- Found and fixed a real backdrop gap: `drawUnderground` skipped columns whose surface row was below
  the viewport, leaving the cleared canvas untouched (pure black). It now fills those columns from the
  top of the view.
- Lifted the cave pattern base and speckles and reduced the depth overlay so unlit cave air is a
  textured blue-grey rather than black.
- Closure evidence: the bottom-left pixel of a 1440x900 render moved from the reported near-black
  family to `rgb(23, 34, 43)`, with visible speckle and strata texture; the prior pure-black stepped
  voids are gone in `tmp/repair-1440-clean2.png`.

### Observation 3 — hotbar names and counts were 8px

- Hotbar names are now 9px at the default size and 10px on large screens; counts are 9px, with 8px
  names kept in the medium breakpoint. The selected name and count remain readable without changing
  the slot grid.
- Closure evidence: `tmp/repair-1440-clean2.png` and `tmp/visual-hover-place.png` show the larger
  names/counts; the 960x600 page check still fits with no HUD clipping.

### Observation 4 — mine-hover cue was subtle on grass

- Strengthened the mine outline: a subtle amber interior wash, a stronger pulsing outer edge, a
  brighter inner edge and four cream corner brackets.
- Strengthened the placement ghost: higher texture opacity, a cool interior tint and a brighter
  dashed green edge, so even Glass reads as a preview.
- Closure evidence: `tmp/visual-hover-mine.png` and `tmp/visual-hover-place.png` show both cues
  clearly at 1182x664.

## Verification after repair

```console
node --test "tests/**/*.test.js"
python tools/page_check.py --screenshot <workbench>/tmp/repair-960.png
```

- Logic: `tests 33`, `pass 33`, `fail 0`.
- Page check: `ok=true`; static problems `[]`; status pixel `[46, 204, 113]` distance `0.0`;
  canvas colour buckets `299`.
- Browser interaction probe: 21/21 checks passed again, including mine, place, player-body refusal,
  out-of-reach refusal, save/reload restore, field-guide open/close, and seed regeneration; no
  console errors.
- No seed test, functional rule, external reference or `#status` behavior changed.

## Conclusion

All four review observations are closed with rendered evidence. The page remains within the approved
scope and is ready for the final independent confirmation.
